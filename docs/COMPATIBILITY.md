# Compatibility

## Version 1.1.3 baselines

| Build target | YouTube version | Supported iOS |
| --- | --- | --- |
| `ios16` | 21.33.6 | 16 and newer |
| `ios17` | 21.41.5 | 17 and newer |

The manual IPA workflow requires a supplied HTTPS URL for the iOS 16 base.
Supplying the optional iOS 17 URL builds both targets with distinct artifact
names. No proprietary IPA URLs are bundled in the workflow. Before injection,
the workflow checks the bundle identifier, exact YouTube version, and minimum
iOS version. Changing Info.plist alone cannot lower an application's actual
OS requirements.

The YTKACE dylib itself targets iOS 15 and can be repacked into an older
YouTube baseline that also targets iOS 15.

## Architectures

YTKACE builds arm64, including for devices that support arm64e.

## YouTube updates

YouTube's internal classes are private and can change without notice. Hooks
resolve classes and selectors at runtime and fail closed. A missing class
disables one feature instead of terminating the app.

## Install paths

The same repacked IPA can be installed through TrollStore, AppSync-compatible
installers, or re-signed by a developer-certificate sideloader. No runtime
injection environment is required.
