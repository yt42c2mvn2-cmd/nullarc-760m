# NullArc Installer v0.3.2 — precompiled Sequoia HP edition

The official v0.3.2 AppKit .app ships with the checksum-pinned, previously compiled 0.2.0 HP Sequoia release. Users do not need a source checkout, Homebrew, an Apple SDK, Mesa development dependencies or a compiler to use the installer.

**Scope:** HP Envy x360 16-ad0013dx, Radeon 760M, macOS Sequoia 15.8.2. This is an experimental driver, not a general hardware installer. Other laptops, Tahoe, and the newer hardware-profile and ACPI brightness source changes are not included or validated in this compiled driver.

## Download and launch

1. Download the `nullarc-760m-appkit-precompiled-v0.3.2-alpha.zip` asset from the `v0.3.2-appkit-precompiled-alpha` GitHub release. Verify `SHA256SUMS-appkit-precompiled` before opening it.
2. Extract the archive and open `NullArcInstaller.app`. The bundled app is ad-hoc-signed, not Apple-notarized. Review the app source and use macOS's normal local-app approval if Gatekeeper prompts you.
3. Click **Prepare Package**. The app checks the embedded 0.2.0 ZIP against its SHA-256 and extracts into a newly created Application Support folder to avoid extra files corrupting the strict package inventory. The extracted `package-manifest.json` is verified using the packaged `package_manifest.py`. The existing installation scripts require Python 3.
4. On an idle, diagnostic-only firmware-framebuffer HP boot, click **Install Files**. The app runs `./install.sh --fresh-files --check`, asks for confirmation and macOS administrator authorization, then stages the precompiled driver files using `./install.sh --fresh-files`. The existing checks and backups remain mandatory.
5. **Installation is staged**: native kernel collection loading, native compute/render, GUI Metal verification and app-startup validation are *not* automatically performed by Install Files. After completing the documented validation stages, click **Enable App Startup**; its guarded `--hp-native` installer may require another boot.
6. Once an app-mode boot passes its live Metal validation, click **Enable Desktop**. It first runs `--windowserver --check`, then requests explicit authorization to arm guarded accelerated WindowServer. It may stage another app-only reboot first. Hardware failures cancel persistence.

## Safety and provenance

- The bundled ZIP is the previously published `nullarc-760m-0.2.0-sequoia-beta-startup-readiness.zip`, not a new compilation of the November 14 hardware discovery, ACPI brightness, or WindowServer persistence source.
- No source fetching or dependency installation is required for the compiled app. The app itself does not change EFI, remove failed-boot markers, bypass AMFI/SIP, or issue GPU register writes. Administrator authorization is requested separately for each allowed install stage.
- Do not run fresh-file staging on an already accelerated desktop. Keep a backup EFI, a firmware framebuffer recovery path and the component backups. No one-click fresh-install GPU activation is promised.
- If package integrity, live driver compatibility, display safety or current-boot validation fails, the existing installer refuses the operation. Do not bypass the refusal.

## Maintainer build

The macOS 15 release workflow fetches the pinned original 0.2.0 compiled ZIP and SHA256SUMS from the existing release. It verifies SHA-256, embeds both files unchanged in the native AppKit .app, compiles just the small Swift frontend with `xcrun swiftc`, ad-hoc signs the complete bundle, checks its embedded resources, creates a ZIP and verifies it after publication. It does **not** build, replace or claim newer GPU binaries.

Locally, from a repository checkout on a macOS machine with Xcode command-line tools:

```sh
bash apps/NullArcInstaller/build.sh build/apps \
  /path/to/nullarc-760m-0.2.0-sequoia-beta-startup-readiness.zip \
  /path/to/SHA256SUMS-startup-readiness
open build/apps/NullArcInstaller.app
```

A build without the two pinned inputs intentionally produces a GUI-only development app which refuses to prepare missing embedded drivers.
