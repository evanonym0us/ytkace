# YTKACE v1.1.3 fork integration

## History and retained changes

The upstream release tag resolves to `68d741a5e54e2a92c64539fe1484436a7d43f20e`.
It adds 82 commits to fork main `be74258b86e7d11958101b5068e0262dbdc59263`.
The merge keeps both histories, including fork commits `b825576` and `be74258`.

The SABR merge conflict was resolved by retaining the bounded request caches,
count-only header logging, and structural body summaries alongside upstream's
exact-session matching, TV client fallback, and playback recovery. HTTPS and
YouTube/Googlevideo destination validation remains at response assignment,
request dispatch, and SABR redirect handling. Raw protobuf debug dumps and raw
directive logging remain disabled. Backup restore limits, preference filtering,
and the Application Support preference for diagnostic logs are retained.
Applying settings still sends the preferences notification and dismisses the
controller without terminating YouTube.

Upstream's functional `sabr-seed.plist` cache is retained in Application Support,
protected until first unlock, and excluded from system backups. It is distinct
from the removed raw debug dumps.

Upstream replaced the playback watchdog in v1.0.0 and deleted its C++ sources
and test. The stale fork CI command was removed; the Python security tests
remain in the Deb workflow. No separately applied workflow security changes
were found in the fork's remote branches or the earlier local work inspected.

## Workflow changes

- iOS 16 uses YouTube 21.33.6; iOS 17+ uses 21.41.5. Artifact names remain distinct.
- Manual inputs have no bundled IPA URLs. Invalid input stops before building.
- Planning emits target labels only, keeping supplied URLs out of matrix values.
- Downloads require HTTPS throughout redirects. The repository token is sent
  only to its exact GitHub release-asset API endpoint and never forwarded on redirects.
- Packaging verifies the YouTube bundle identifier, exact version, and compatible
  minimum OS before injection.
- Checkout credentials are not persisted. Workflow permissions remain read-only.
- Pull requests test and compile rootless and roothide packages. The IPA workflow
  stays manual and is not called by pull-request CI.

## Checks without proprietary IPAs

Run from the repository root:

```sh
python3 -m unittest discover -s Tests -v
git diff --check
for script in Scripts/*.sh Tools/*.sh; do bash -n "$script"; done
```

The suite contains 21 tests. Download transport is mocked, and archive fixtures
contain only synthetic Info.plist data. No real IPA or live download is required.
The existing Mach-O injection tests use synthetic binary data.

With a configured Theos toolchain, compile the tweak alone:

```sh
make clean
make package FINALPACKAGE=1 THEOS_PACKAGE_SCHEME=rootless DISABLE_ROOTLESS_COMPAT_WARNING=1
make clean
make package FINALPACKAGE=1 THEOS_PACKAGE_SCHEME=roothide DISABLE_ROOTLESS_COMPAT_WARNING=1
```

These package builds do not fetch YouTube. The dylib retains upstream's iOS 15
deployment target, which is compatible with both requested iOS versions.

## Device regression checks still required

Use an already installed, authorized base on iOS 16 / YouTube 21.33.6 and
iOS 17+ / YouTube 21.41.5. Static checks and package compilation cannot prove
private YouTube UI selectors work on a device.

1. Toggle a setting and apply: settings dismiss, playback continues, and the
   preference takes effect. Open settings again to confirm persistence.
2. On both old and new Shorts UI, confirm the download button appears, Auto-Skip
   advances, Play Shorts Once stops repeating, and pinch fullscreen enters/exits
   without freezing or switching to the next Short.
3. Check ordinary playback, background playback, PiP, download/resume after
   relaunch, TV-client fallback, and loop with Local Queue enabled.
4. Enable Hide AI Channels and its optional warnlist; verify feed and search
   filtering and behavior when the list refresh is unavailable.
5. Check SponsorBlock popup fade-in and swipe dismissal, plus player chapter
   appearance. Confirm backup restore accepts valid data and rejects oversized
   archives and unrelated preference keys.

The IPA packaging workflow was not executed during this integration. No
proprietary IPA files were downloaded or inspected for testing.
