# NullArc-760M 0.3.0 — Sequoia source preview

**Experimental source prerelease. NOT a precompiled or validated graphics-driver installer.**

Source branch: `codex/760m-hardware-discovery-backlight`.
Source scope: ten development commits after `d017ecf53ba4d4a1cecc6b06e3543c94aeacfaf5`, plus this release documentation and publication workflow.

## Changes

- Guarded persistent WindowServer arming and recovery: recent boot status, success/presentation checks, login-session transition retries, duplicate-supervisor handling, panic evidence and safer NVRAM failure handling. New state-machine tests simulate successive verified accelerated boots and real failure fallback.
- Expanded hardware identification: reviewed board registry, isolated initialization contracts, read-only macOS/Linux AMD GPU collector, conservative unknown-device behavior, validated memory/display profile structures and RADV profile dispatch. **This is not confirmed support for Dell, ASUS, Lenovo or new Radeon devices.**
- Experimental native ACPI backlight bridge for internal displays: validates ACPI LCD routing, published levels and readback; handles bounded changes and power events. **There is no verified physical brightness, macOS slider, keyboard-key, sleep/wake or reboot test.** DCN PWM, eDP AUX and vendor-specific key backends remain unimplemented.
- Source-side Metal/Vulkan pipeline-cache and timing improvements, with additional host tests.
- Preserve the existing HP 760M native/Metal/WindowServer evidence and rollback protections; the new native changes are not claimed to be runtime-verified.

## What is included

- `nullarc-760m-v0.3.0-sequoia-source-preview.zip`: complete Git-tracked source snapshot at this release tag, including new profile data, Python tools, kernel/Metal changes, patches and tests
- `SHA256SUMS-source-preview`: SHA-256 checksum for the source ZIP
- GitHub's automatically generated source archives

**This ZIP is a source tree, not the 0.2.0 compiled installer.** It does not contain updated, ready-to-install compiled PhxAccel.kext, PhxBringup.kext, NVMTLDriver.bundle or RADV matching these source changes. Do not treat the prior binary release as if it were rebuilt with native ACPI brightness or generic hardware support.

## Validation and remaining work

The included source changes have documented host/mock and build validation. Release publication runs focused Python regression tests, C dispatch tests and a source archive integrity check. This does not execute GPU commands on a real laptop.

Before an installable 0.3.0 binary release: rebuild and package matching native artifacts (kexts, plugin, RADV, translator/dependencies), generate/verify a manifest and checksums, validate on the actual HP with an idle diagnostic/fallback path, complete *two consecutive* accelerated WindowServer boots, and test brightness with supported hardware. Unknown laptops must remain read-only/diagnostic-only until independently validated.

For the existing compiled and previously tested HP Sequoia package, continue to use [v0.2.0-sequoia-beta](https://github.com/yt42c2mvn2-cmd/nullarc-760m/releases/tag/v0.2.0-sequoia-beta). Do not delete working driver files or bypass failure markers to try source-only changes.

See `docs/HARDWARE_SUPPORT.md`, `docs/760M_STATUS.md`, `docs/INSTALL.md`, and `README.md` for boundaries and exact hardware evidence. macOS Tahoe 26 is not validated on the HP.
