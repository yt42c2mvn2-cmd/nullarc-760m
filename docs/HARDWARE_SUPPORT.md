# Hardware-aware Radeon support and native backlight development

## Current support boundary (2026-11-14)

| Hardware / feature | Evidence and activation |
| --- | --- |
| HP Envy x360 16-ad0013dx, `1002:1900/ca`, `103c:8c6a` | Previous native GPU, Metal and WindowServer hardware evidence retained. This revision is host-tested and compiled, **not installed or runtime-tested**. Persistence repair still needs the two consecutive accelerated boots recorded in STATUS. |
| Firebat U6C 780M, `1002:1900/ba`, `8001:2014` | Existing upstream reference implementation retained for its captured identity. No new hardware verification. |
| Other HP, Dell, ASUS, Lenovo and other AMD laptops | Read-only discovery; no automatic native initialization or display takeover. Manufacturer names, matching device IDs and eight CUs do not establish compatibility. |
| Native ACPI brightness bridge | Implemented and compiled; **no physical brightness, slider, keyboard, persistence or sleep/wake test has been completed**. |
| DCN PWM / eDP AUX brightness, OEM-only keys | Not implemented. No unverified register writes, AUX transactions or OEM ACPI method calls. |

The published beta and the installed HP system are unchanged. This branch does
not establish full device support or add verified manufacturers.

## Architecture

`hardware/devices/registry.json` selects a reviewed board contract, rather than
making an unknown `1900` device inherit Firebat initialization. The generated
`phx_hardware_registry.inc` is consumed by PhxBringup, NMXAccel and PhxAMDFB.
Identity is one input: live firmware/reservation matching, exclusive PCI ownership,
VRAM leases, firmware acknowledgements, queue fences, shader readbacks, GUI Metal
and display presentation are still separate requirements.

An unknown board publishes a diagnostic service without PCI command writes or
mapping its GPU register/doorbell/VRAM apertures. QueryInfo refuses to fabricate
reference capabilities. Its native bootstrap, accelerator attachment and framebuffer
takeover are blocked. The installer also refuses to route an unreviewed device
or ambiguous multiple-device selection through the reference installer.

`PhxMemoryProfile` separates captured memory/firmware constraints from their
validator. Additional sorted, nonoverlapping reserved intervals are excluded
before leasing; ranges crossing the CPU aperture are clipped safely. The existing
HP addresses, masks and exclusion are preserved. Address decoding alone is never
an ownership assertion.

`PhxDisplayProfile` supplies validated register addresses, expected samples,
geometry, pitch, timings and scanout offset to the shared console planner.
Geometry must match the actual platform console, timings must be coherent, and
the entire scanout must fit the verified exclusion and apertures. Generic AGDC
queries no longer invent a 2560×1600 panel when no framebuffer has published.
The reference path's existing timing fallback remains confined to that profile.
This is firmware-mode takeover, not new mode setting, AUX routing or external
monitor support.

RADV patch 0014 uses generated `phx_radv_profiles.h` instead of selecting device
properties only by HP identity. The generator cross-checks the topology and
measured device-info capture, including physical CU masks. Unknown or mismatched
captured topology fails device-info enumeration; the legacy reference mock remains
unchanged. The Metal/AIR translator and existing RADV submission/resource code do
not need another implementation for each laptop manufacturer.

## Read-only collection (no sudo or installation)

On macOS or Linux:

```sh
python3 tools/collect_hardware.py --output ~/nullarc-hardware.json
```

An assembled package also provides:

```sh
./install.sh --hardware-report ~/nullarc-hardware.json
```

Use a new filename. Reports are created exclusively with mode 0600. The collector
records AMD display PCI identities, available BAR/resource properties, published
memory/firmware state, EDID checksums and preferred geometry/timings. Linux also
collects IP discovery, DRM connector state/modes and PCI-associated backlight
attributes. Missing data is null/absent or an explicit error. The collector issues
no MMIO, firmware commands, ACPI methods, submissions, driver loads or resets.
Inspect reports before sharing; selected display parameters and EDID hashes can
identify a panel. Nothing is uploaded.

For Linux CU masks and full kernel-reported device properties, build the existing
query-only DRM helper once (requires distribution libdrm development headers):

```sh
cc -std=c11 -Wall -Wextra -Werror $(pkg-config --cflags libdrm) \
  tools/linux-profile/collect.c -o /tmp/nullarc-drm-info
python3 tools/collect_hardware.py --drm-collector /tmp/nullarc-drm-info \
  --output ~/nullarc-hardware-linux.json
```

The collector locates each device's render node and cross-checks DRM against its
PCI identity. The detailed Linux evidence collector also autodetects a unique AMD
render node and no longer requires the HP subsystem ID. Its result is evidence,
not a macOS memory-ownership or firmware-compatibility certificate.

## Adding a validated profile

1. Collect macOS and Linux facts. Preserve unknown values; do not infer retail
   models or physical CU positions from a PCI ID or CU count.
2. Add topology and device-info evidence. Supply a reviewed contract under
   `hardware/devices/contracts`: supported initialization backend/IP versions,
   configuration headers/symbols, topology source and matching device-info capture.
3. Supply memory/display data through the shared profile structures. Validate
   **all** firmware, live display/cursor/DMCUB reservations, active routing and
   allocator exclusions. There must be no collision with PSP/MES/staging/TMR space.
   A different firmware/engine protocol needs a new reviewed backend, not a data
   override of Phoenix native39.
4. Add the exact identity and contract to the registry; run
   `python3 tools/phx_hardware_registry.py --write`. Review generated kernel and
   RADV data together. Reports cannot dynamically register a native profile.
5. Add positive and negative fixtures and test changed firmware, reservations,
   CU masks, timings, unsupported IDs and failures. Rebuild the relevant components
   and regenerate Mesa patch 0014 if the registry changes.
6. Validate a diagnostic boot before any initialization; perform native and Metal
   readbacks before app activation, then a guarded display test with recovery.

The installation/startup/recovery orchestration remains the reviewed HP path.
A second board still needs its runtime preflight and boot authorization adapted
and physically validated. The generic profile structures do not authorize using
`hp_bringup.py`, HP recovery scripts or persistent WindowServer arming on it.
No Dell/ASUS/Lenovo native profile has been fabricated to bypass that boundary.

## Native brightness implementation

`phxbacklight.cpp` implements Apple's `IODisplayParameterHandler` on the panel's
PhxAMDFB. It follows the PCI device's actual ACPI peer, binds a unique internal
LCD route through `_DOD`/`_ADR` (standard or legacy LCD ID), requires active `_DCS`,
a valid `_DDC` base EDID matching console geometry, `_BCL`, `_BQC` and `_BCM`, and
checks the runtime parameter-handler ABI. Ambiguous routes, invalid levels,
index-valued/unknown `_BQC` formats and unsupported methods remain diagnostic.
It does not select a global PNLF or guess OEM methods.

Only that framebuffer's `IOBacklightDisplay` receives `brightness`. The service
is named `backlight` before IOFramebuffer starts, advertises the native LCD sense,
and supplies its validated base EDID. This is the macOS path used by System
Settings/Control Center and already recognized HID brightness keys; no third-party
brightness utility is used. OEM key events without a standard HID mapping are not
yet bridged. Actual UI publication and keys require hardware verification.

Brightness writes run on a worker outside the framebuffer/UI lock. Only advertised
positive `_BCL` levels are used; at most twelve bounded steps approach a target.
Each `_BCM` must succeed and `_BQC` must match; a failure stops further writes.
Power dimming does not overwrite the user's target. Sleep cancels/waits for the
worker; wake restores the target only through the same validated readback path.
A debounced NVRAM record binds the advertised level to all five PCI identity
fields and the full base EDID. Unsupported NVRAM is reported, not retried in a loop.
Reboot retention is unverified and depends on working platform NVRAM.

The HP's read-only ACPI inventory exposes `VGA/LCD@110`; it does **not** prove that
its methods control brightness. The candidate supports `-phxbacklightoff` to leave brightness untouched.
No candidate kext or brightness write was tested
on it. Native DCN PWM/AUX needs a verified link/panel backend; its absence is not
replaced with guessed registers. External panels receive no backlight handler.

## Validation and remaining hardware work

`make test` includes manufacturer/identity isolation, profile/capture consistency,
synthetic alternate panel geometry and memory, exclusion collisions, ACPI routing,
malformed ranges, readback failures and panel-bound saved levels, alongside the
existing HP persistence/recovery tests. These are host tests, not GPU execution.

Both kexts and patched RADV build locally. RADV's host transport tests and 8-CU /
12-CU gfx1103 ACO compiler tests pass with zero GPU submissions. The translator's
working native binary is unchanged. Hardware validation still requires an
explicitly authorized backed-up candidate installation, HP regression boots and
physical slider/key/persistence/sleep tests; other manufacturers also require
their own firmware/reservation/routing evidence. No new installation was performed.

## Reference study

NullMoth's [layered design](https://github.com/nullmoth/nvidia-macos-driver/blob/main/docs/HOW-IT-WORKS.md),
[device/start gates](https://github.com/nullmoth/nvidia-macos-driver/blob/main/kexts/NVRM/nvrm_devtab.h)
and [startup policy](https://github.com/nullmoth/nvidia-macos-driver/blob/main/kexts/NVRM/nvrm_startup_policy.h)
separate device ownership, firmware readiness, connector enumeration and display
publication. Those architectural ideas inform the profile and readiness separation
here. NVIDIA GSP/NVKMS, BAR relocation, firmware versions and DPCD implementation
were not copied into the AMD driver.

The backlight bridge uses the public [Apple IODisplay interfaces](https://github.com/apple-oss-distributions/IOGraphics/blob/main/IOGraphicsFamily/IODisplay.cpp)
and [IOBacklightDisplay integration](https://github.com/apple-oss-distributions/IOGraphics/blob/main/IOGraphicsFamily/IOBacklightDisplay.cpp),
with ACPI method semantics cross-checked against [Linux ACPI video](https://github.com/torvalds/linux/blob/master/drivers/acpi/acpi_video.c).
No NullMoth noncommercial backlight source is imported.
