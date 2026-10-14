import importlib.util
import io
import pathlib
import plistlib
import tempfile
import unittest
import urllib.error
import urllib.request
import zipfile
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("ipa_workflow", ROOT / "Tools/ipa_workflow.py")
IPA = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IPA)
URL = "https://example.invalid/base.ipa?signature=test"
REPO = "evanonym0us/ytkace"
ASSET = f"https://api.github.com/repos/{REPO}/releases/assets/123"


def synthetic_archive(version="21.33.6", minimum="16.0", bundle="com.google.ios.youtube"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("Payload/Synthetic.app/Info.plist", plistlib.dumps({
            "CFBundleIdentifier": bundle,
            "CFBundleShortVersionString": version,
            "MinimumOSVersion": minimum,
        }))
    return output.getvalue()


class IPAWorkflowTests(unittest.TestCase):
    def test_plan_preserves_one_or_both_targets_without_exposing_urls(self):
        self.assertEqual(IPA.plan(URL, ""), [{"label": "ios16"}])
        self.assertEqual(IPA.plan(URL, URL), [{"label": "ios16"}, {"label": "ios17"}])

    def test_plan_requires_an_explicit_ios16_base(self):
        with self.assertRaises(ValueError):
            IPA.plan("", URL)

    def test_unsafe_inputs_are_rejected_for_either_target(self):
        for url in ("http://example.invalid/base.ipa", "https://user:pass@example.invalid/a",
                    "https://example.invalid:8443/a", "https:///a", "file:///a",
                    URL + "\n", "https://example.invalid/a#fragment",
                    "https://example.invalid\\@other.invalid/a"):
            for inputs in ((url, ""), (URL, url)):
                with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                    IPA.plan(*inputs)

    def test_token_is_only_sent_to_exact_repository_asset_endpoint(self):
        self.assertEqual(IPA.request_headers(ASSET, REPO, "test-token")["Authorization"],
                         "Bearer test-token")
        for url in (URL, ASSET.replace(REPO, "other/repo"), ASSET + "/suffix",
                    ASSET + "?redirect=elsewhere", ASSET.replace("api.github.com", "api.github.com.evil.invalid")):
            with self.subTest(url=url):
                self.assertNotIn("Authorization", IPA.request_headers(url, REPO, "test-token"))

    def test_redirects_drop_credentials_and_block_https_downgrades(self):
        request = urllib.request.Request(ASSET, headers={"Authorization": "Bearer test-token"})
        handler = IPA.HTTPSRedirectHandler()
        for target in (URL, ASSET + "4"):
            redirected = handler.redirect_request(request, None, 302, "Found", {}, target)
            self.assertIsNone(redirected.get_header("Authorization"))
        with self.assertRaises(ValueError):
            handler.redirect_request(request, None, 302, "Found", {}, "http://example.invalid/a")

    def test_download_uses_mocked_transport_and_accepts_synthetic_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "synthetic.zip"
            opener = mock.Mock()
            opener.open.return_value = io.BytesIO(synthetic_archive())
            with mock.patch.object(IPA.urllib.request, "build_opener", return_value=opener):
                IPA.download(URL, path, REPO, "test-token")
            self.assertTrue(zipfile.is_zipfile(path))
            request = opener.open.call_args.args[0]
            self.assertIsNone(request.get_header("Authorization"))

    def test_failed_downloads_remove_partial_files(self):
        for result in (b"not a zip", urllib.error.URLError("synthetic failure")):
            with self.subTest(result=result), tempfile.TemporaryDirectory() as directory:
                path = pathlib.Path(directory) / "synthetic.zip"
                path.write_bytes(b"partial")
                opener = mock.Mock()
                if isinstance(result, Exception):
                    opener.open.side_effect = result
                else:
                    opener.open.return_value = io.BytesIO(result)
                with mock.patch.object(IPA.urllib.request, "build_opener", return_value=opener):
                    with self.assertRaises((ValueError, urllib.error.URLError)):
                        IPA.download(URL, path, REPO, "")
                self.assertFalse(path.exists())

    def check_name(self, data, label):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "synthetic.zip"
            path.write_bytes(data)
            return IPA.artifact_name(path, label, "1.1.3")

    def test_compatible_bases_get_distinct_release_names(self):
        self.assertEqual(self.check_name(synthetic_archive(), "ios16"),
                         "YTKACE_1.1.3_YouTube_iOS16_21.33.6.ipa")
        self.assertEqual(self.check_name(synthetic_archive("21.41.5", "17.0"), "ios17"),
                         "YTKACE_1.1.3_YouTube_21.41.5.ipa")

    def test_rejects_wrong_app_version_and_incompatible_minimum_os(self):
        for version, minimum, bundle in (("21.41.5", "17.0", "com.google.ios.youtube"),
                                         ("21.33.6", "16.1", "com.google.ios.youtube"),
                                         ("21.33.6", "", "com.google.ios.youtube"),
                                         ("21.33.6", "16.0", "other.app")):
            with self.subTest(version=version, minimum=minimum, bundle=bundle):
                with self.assertRaises(ValueError):
                    self.check_name(synthetic_archive(version, minimum, bundle), "ios16")

    def test_rejects_ambiguous_top_level_apps(self):
        output = io.BytesIO(synthetic_archive())
        with zipfile.ZipFile(output, "a") as archive:
            archive.writestr("Payload/Other.app/Info.plist", plistlib.dumps({}))
        with self.assertRaises(ValueError):
            self.check_name(output.getvalue(), "ios16")


if __name__ == "__main__":
    unittest.main()
