#!/usr/bin/env python3
"""Plan and validate manually supplied IPA bases; tests never need a real IPA."""

import argparse
import json
import os
import pathlib
import plistlib
import re
import shutil
import sys
import urllib.parse
import urllib.request
import zipfile


TARGETS = {"ios16": "21.33.6", "ios17": "21.41.5"}


def validate_url(url):
    if not url or any(ord(char) <= 32 for char in url) or "\\" in url:
        raise ValueError("IPA URLs must be HTTPS URLs without whitespace")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.port not in (None, 443)
            or parsed.fragment):
        raise ValueError("IPA URLs must use HTTPS without credentials or fragments")
    return parsed


def plan(ios16_url, ios17_url):
    validate_url(ios16_url)
    targets = [{"label": "ios16"}]
    if ios17_url:
        validate_url(ios17_url)
        targets.append({"label": "ios17"})
    return targets


def request_headers(url, repository, token):
    parsed = validate_url(url)
    headers = {"Accept": "application/octet-stream"}
    # Never send the repository token to arbitrary input URLs or API paths.
    asset_path = rf"/repos/{re.escape(repository)}/releases/assets/[0-9]+"
    if (token and parsed.hostname == "api.github.com" and not parsed.query
            and re.fullmatch(asset_path, parsed.path)):
        headers["Authorization"] = f"Bearer {token}"
    return headers


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        validate_url(new_url)
        redirected = super().redirect_request(request, fp, code, message, headers, new_url)
        if redirected is not None:
            # Release assets redirect to storage hosts; never forward API credentials.
            redirected.remove_header("Authorization")
        return redirected


def download(url, destination, repository, token):
    request = urllib.request.Request(url, headers=request_headers(url, repository, token))
    opener = urllib.request.build_opener(HTTPSRedirectHandler())
    destination = pathlib.Path(destination)
    try:
        with opener.open(request, timeout=60) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
        if not zipfile.is_zipfile(destination):
            raise ValueError("The supplied file is not an IPA ZIP archive")
    except Exception:
        destination.unlink(missing_ok=True)
        raise


def artifact_name(ipa, label, tweak_version):
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", tweak_version):
        raise ValueError("Invalid tweak version")
    with zipfile.ZipFile(ipa) as archive:
        infos = [name for name in archive.namelist()
                 if re.fullmatch(r"Payload/[^/]+\.app/Info\.plist", name)]
        if len(infos) != 1:
            raise ValueError("Expected exactly one top-level application")
        info = plistlib.loads(archive.read(infos[0]))
    if info.get("CFBundleIdentifier") != "com.google.ios.youtube":
        raise ValueError("The supplied base must be YouTube")
    if info.get("CFBundleShortVersionString") != TARGETS[label]:
        raise ValueError(f"{label} requires YouTube {TARGETS[label]}")
    minimum = str(info.get("MinimumOSVersion", ""))
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", minimum):
        raise ValueError("Missing or invalid MinimumOSVersion")
    os_version = tuple(int(part) for part in minimum.split("."))
    os_version += (0,) * max(0, 3 - len(os_version))
    if os_version > (int(label[3:]), 0, 0):
        raise ValueError(f"This base does not support {label}")
    marker = "iOS16_" if label == "ios16" else ""
    return f"YTKACE_{tweak_version}_YouTube_{marker}{TARGETS[label]}.ipa"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "download", "name"))
    parser.add_argument("--target", choices=TARGETS)
    parser.add_argument("--ipa", default="YouTube.ipa")
    parser.add_argument("--tweak-version")
    args = parser.parse_args()
    if args.command == "plan":
        targets = plan(os.environ.get("IPA_URL", ""), os.environ.get("IPA_URL_IOS17", ""))
        # Keep signed URLs out of matrix values and job names.
        print("targets=" + json.dumps(targets))
    elif args.target is None:
        parser.error("--target is required")
    elif args.command == "download":
        variable = "IPA_URL" if args.target == "ios16" else "IPA_URL_IOS17"
        download(os.environ.get(variable, ""), args.ipa,
                 os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GH_TOKEN", ""))
    else:
        print(artifact_name(args.ipa, args.target, args.tweak_version or ""))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Network exceptions can contain signed URLs. Do not print them to CI logs.
        print(f"IPA input validation or processing failed ({type(error).__name__})", file=sys.stderr)
        sys.exit(1)
