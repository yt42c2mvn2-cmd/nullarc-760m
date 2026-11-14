# NullArc Installer — minimal native AppKit frontend

This is a small **x86_64 macOS AppKit utility** written in Swift. It is not an Electron app, does not embed a web server, and has no resident privileged daemon, login item, driver, Python environment or other dependencies of its own.

## Build the app (macOS + Xcode command line tools)

From the repository checkout:

```sh
bash apps/NullArcInstaller/build.sh
open build/apps/NullArcInstaller.app
```

The build script uses `xcrun swiftc`, produces an ad-hoc-signed x86_64 .app, and does not install anything. Official alpha release ZIPs can contain this app precompiled. It is **not notarized**; macOS may require the standard right-click/Open override for locally built software.

## Use the GUI with a released, compiled package

1. Download the approved compiled 0.2.0 Sequoia HP ZIP and SHA256SUMS from the release page; verify the archive checksum and extract it into a clean directory. Do not substitute an unverified source-only ZIP for native binaries.
2. Click **Choose Package** and select the directory containing `install.sh`, `package_manifest.py` and `package-manifest.json`.
3. Click **Verify Package**. The GUI runs the package's existing SHA-256 inventory verifier, without privilege or GPU initialization.
4. For a **fresh** HP diagnostic-only install, use **Check Files** then **Install Files**. This invokes `install.sh --fresh-files --check` before presenting a clear macOS administrator authorization prompt to run `install.sh --fresh-files`; it archives recognized old components and boot service but does not rebuild/load auxiliary kexts, activate GPU queues, arm display or override safety markers.
5. Only after the documented manual engine, loaded-kext and Metal verification stages, use **Check App Startup** and **Enable App Startup**. Follow its required app-mode reboot and validation.
6. Only after actual current-boot native/Metal/display checks succeed, choose **Check WindowServer** and **Arm WindowServer**. `install.sh --windowserver` remains the trusted policy gate. It may stage another reboot rather than immediately authorize a display boot. Persistence rearming remains guarded; genuine faults still cancel it.
7. **Read Current Status** reads the last public HP boot report and current NVRAM/kext state without modifying them.

Every installation operation first runs its unprivileged `--check` preflight, then requires an explicit second confirmation. A macOS administrator prompt via the system `osascript` privilege mechanism is used only for the selected install action. The app does **not** retain credentials or impersonate root. The underlying installer independently repeats package validation and guarded runtime checks.

**Never use fresh file staging on an already running accelerated desktop.** An installed bundle is not proof that its kext was loaded. Keep EFI backups and a firmware-framebuffer recovery boot. Do not remove failure markers automatically.

## Compile a fresh driver stack using the same UI

This optional advanced mode needs a real source checkout, macOS build tools, pinned Mesa/RADV checkout, MacKernelSDK, Vulkan headers, glslang, translator source, AIR-runtime dependencies and third-party license material.

1. **Choose Source**: select the repository checkout containing `tools/build_stack.py`.
2. Copy `apps/NullArcInstaller/build-config.example.json` outside the repo and fill in **absolute paths** to your local dependencies. Set `min_macos` to `15.0` for the known Sequoia target; Tahoe 26 is not hardware-validated. Choose an unused absolute output directory.
3. **Choose Build Config** and **Compile GPU Stack**. The app calls the existing `tools/build_stack.py` with arguments (never via a shell), runs it as the logged-in user, and selects the resulting manifest-bearing package if the build succeeds. This is not an installer or a hardware validation claim.
4. **Verify Package**, then follow the same staged installation and runtime testing procedure above. The new hardware-profile and backlight binaries must be evaluated first on diagnostic-only hardware; do not immediately arm WindowServer just because compilation succeeds.

The core `build_stack.py` build requires correctly versioned external sources and binaries; this app is not a one-click downloader and cannot manufacture a matching GPU build without them.

## Supported scope and limitations

- The AppKit GUI is built for Intel x86_64 macOS. Its release ZIP contains **the app only**, not recompiled GPU drivers or firmware.
- The verified and guarded runtime path remains the exact HP Envy x360 Radeon 760M on macOS Sequoia 15. Other laptops remain discovery-only; macOS 26 remains unverified.
- Experimental ACPI brightness and newer persistence fixes in source may require rebuilding kexts and hardware testing. The app does not silently change AMFI, EFI, NVRAM, protected failures or permissions.
- The packaging job compiles and signs the GUI and checks the uploaded ZIP; it cannot prove GPU compatibility, brightness, or successful boot persistence on a physical laptop.
