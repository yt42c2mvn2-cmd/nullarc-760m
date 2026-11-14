import AppKit
import Foundation

// The shipped app contains the already-compiled, checksum-pinned Sequoia 0.2.0
// release. It never compiles GPU code, loads kexts or circumvents install.sh.
final class NullArcInstaller: NSObject, NSApplicationDelegate {
    private let release = "nullarc-760m-0.2.0-sequoia-beta-startup-readiness.zip"
    private let sums = "SHA256SUMS-startup-readiness"
    private let extractedName = "nullarc-760m-0.2.0-sequoia-beta"
    private let workspace = URL(fileURLWithPath: NSHomeDirectory(), isDirectory: true)
        .appendingPathComponent("Library/Application Support/NullArcInstaller", isDirectory: true)

    private var window: NSWindow!
    private let headline = NSTextField(wrappingLabelWithString:
        "Precompiled Radeon 760M driver • no source downloads or compilation")
    private let preparedStatus = NSTextField(wrappingLabelWithString: "Not prepared")
    private let filesStatus = NSTextField(wrappingLabelWithString: "Waiting for package verification")
    private let desktopStatus = NSTextField(wrappingLabelWithString: "Requires native and Metal validation")
    private let activity = NSTextField(labelWithString: "Ready")
    private let spinner = NSProgressIndicator()
    private let console = NSTextView(frame: .zero)
    private var buttons: [NSButton] = []
    private var busy = false
    private var prepared: URL?
    private var advanced: NSView!

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildWindow()
        if let path = UserDefaults.standard.string(forKey: "preparedPackage"),
           FileManager.default.fileExists(atPath: URL(fileURLWithPath: path).appendingPathComponent("package-manifest.json").path) {
            prepared = URL(fileURLWithPath: path)
            preparedStatus.stringValue = "Previously prepared: " + prepared!.lastPathComponent
            filesStatus.stringValue = "Run safety checks before staging any files"
        }
        log("NullArc Installer • precompiled Sequoia 0.2.0 HP package")
        log("Graphics driver installation is guarded. A file install does not immediately enable GPU acceleration.")
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }

    private func text(_ value: String, size: CGFloat = 12, bold: Bool = false,
                      color: NSColor = .labelColor) -> NSTextField {
        let v = NSTextField(wrappingLabelWithString: value)
        v.font = bold ? .boldSystemFont(ofSize: size) : .systemFont(ofSize: size)
        v.textColor = color
        return v
    }
    private func button(_ name: String, _ action: Selector) -> NSButton {
        let b = NSButton(title: name, target: self, action: action)
        b.bezelStyle = .rounded
        b.controlSize = .large
        buttons.append(b)
        return b
    }
    private func row(_ values: [NSView], spacing: CGFloat = 10) -> NSStackView {
        let s = NSStackView(views: values)
        s.orientation = .horizontal
        s.alignment = .centerY
        s.spacing = spacing
        return s
    }
    private func column(_ values: [NSView], spacing: CGFloat = 8) -> NSStackView {
        let s = NSStackView(views: values)
        s.orientation = .vertical
        s.alignment = .leading
        s.spacing = spacing
        return s
    }
    private func icon(_ name: String) -> NSImageView {
        let v = NSImageView()
        v.image = NSImage(systemSymbolName: name, accessibilityDescription: name)
        v.contentTintColor = .systemBlue
        v.translatesAutoresizingMaskIntoConstraints = false
        v.widthAnchor.constraint(equalToConstant: 28).isActive = true
        v.heightAnchor.constraint(equalToConstant: 28).isActive = true
        return v
    }
    private func card(step: String, title: String, help: String, symbol: String,
                      action: Selector, actionTitle: String, state: NSTextField) -> NSView {
        let panel = NSBox()
        panel.boxType = .custom
        panel.cornerRadius = 12
        panel.borderWidth = 1
        panel.borderColor = .separatorColor
        panel.fillColor = .controlBackgroundColor
        panel.contentViewMargins = NSSize(width: 0, height: 0)
        let go = button(actionTitle, action)
        go.widthAnchor.constraint(greaterThanOrEqualToConstant: 150).isActive = true
        state.font = .systemFont(ofSize: 11)
        state.textColor = .secondaryLabelColor
        let inside = column([
            row([icon(symbol), text(step.uppercased(), size: 10, bold: true, color: .secondaryLabelColor)]),
            text(title, size: 18, bold: true),
            text(help, size: 12, color: .secondaryLabelColor),
            go, state
        ], spacing: 10)
        inside.translatesAutoresizingMaskIntoConstraints = false
        guard let container = panel.contentView else { return panel }
        container.addSubview(inside)
        NSLayoutConstraint.activate([
            inside.leadingAnchor.constraint(equalTo: container.leadingAnchor, constant: 16),
            inside.trailingAnchor.constraint(equalTo: container.trailingAnchor, constant: -16),
            inside.topAnchor.constraint(equalTo: container.topAnchor, constant: 16),
            inside.bottomAnchor.constraint(lessThanOrEqualTo: container.bottomAnchor, constant: -16),
            panel.heightAnchor.constraint(greaterThanOrEqualToConstant: 218)
        ])
        return panel
    }
    private func buildWindow() {
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 930, height: 690),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "NullArc Installer"
        window.minSize = NSSize(width: 780, height: 615)
        window.titlebarAppearsTransparent = true

        let base = NSVisualEffectView()
        base.material = .windowBackground
        base.blendingMode = .behindWindow
        base.state = .active
        window.contentView = base
        let stack = column([], spacing: 15)
        stack.translatesAutoresizingMaskIntoConstraints = false
        base.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: base.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: base.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: base.topAnchor, constant: 24),
            stack.bottomAnchor.constraint(equalTo: base.bottomAnchor, constant: -22)
        ])
        let name = text("NullArc", size: 26, bold: true)
        let edition = text("760M  •  PRECOMPILED SEQUOIA BETA", size: 11, bold: true, color: .secondaryLabelColor)
        headline.font = .systemFont(ofSize: 12)
        headline.textColor = .secondaryLabelColor
        stack.addArrangedSubview(row([icon("cpu"), column([name, edition, headline], spacing: 3)], spacing: 15))

        let stages = row([
            card(step: "Step 1", title: "Prepare", help: "Verify and unpack the included driver ZIP.",
                 symbol: "shippingbox", action: #selector(prepare),
                 actionTitle: "Prepare Package", state: preparedStatus),
            card(step: "Step 2", title: "Install files", help: "Back up and stage drivers on an idle HP boot.",
                 symbol: "internaldrive", action: #selector(installFiles),
                 actionTitle: "Install Files…", state: filesStatus),
            card(step: "Step 3", title: "WindowServer", help: "Arm only after proven GPU and Metal startup.",
                 symbol: "display", action: #selector(armDesktop),
                 actionTitle: "Enable Desktop…", state: desktopStatus)
        ], spacing: 12)
        stages.distribution = .fillEqually
        stages.translatesAutoresizingMaskIntoConstraints = false
        stack.addArrangedSubview(stages)
        stages.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true

        let note = text("An idle diagnostic boot is required for file staging. Full acceleration still needs the documented kernel collection, native/Metal verification and app-startup steps. Nothing bypasses safety markers.", size: 12, color: .secondaryLabelColor)
        stack.addArrangedSubview(note)
        stack.addArrangedSubview(row([
            button("Enable App Startup…", #selector(enableStartup)),
            button("Read System Status", #selector(systemStatus)),
            button("Show Package", #selector(showPackage)),
            button("Advanced", #selector(toggleAdvanced))
        ]))
        let extra = row([
            button("Verify Package", #selector(verifyPrepared)),
            button("Check File Install", #selector(checkFiles)),
            button("Check App Startup", #selector(checkStartup)),
            button("Check WindowServer", #selector(checkDisplay))
        ])
        extra.isHidden = true
        advanced = extra
        stack.addArrangedSubview(extra)

        let separator = NSBox()
        separator.boxType = .separator
        stack.addArrangedSubview(separator)
        separator.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isDisplayedWhenStopped = false
        spinner.widthAnchor.constraint(equalToConstant: 16).isActive = true
        activity.font = .systemFont(ofSize: 12)
        activity.textColor = .secondaryLabelColor
        stack.addArrangedSubview(row([spinner, activity]))
        console.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        console.isEditable = false
        console.isSelectable = true
        console.textContainerInset = NSSize(width: 8, height: 8)
        let scroll = NSScrollView()
        scroll.borderType = .bezelBorder
        scroll.hasVerticalScroller = true
        scroll.documentView = console
        scroll.translatesAutoresizingMaskIntoConstraints = false
        stack.addArrangedSubview(scroll)
        NSLayoutConstraint.activate([
            scroll.widthAnchor.constraint(equalTo: stack.widthAnchor),
            scroll.heightAnchor.constraint(greaterThanOrEqualToConstant: 180)
        ])
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
    private func log(_ line: String) {
        let value = line.hasSuffix("\n") ? line : line + "\n"
        console.textStorage?.append(NSAttributedString(string: value))
        console.scrollRangeToVisible(NSRange(location: max(0, console.string.utf16.count - 1), length: 0))
    }
    private func alert(_ title: String, _ detail: String) {
        let sheet = NSAlert()
        sheet.messageText = title
        sheet.informativeText = detail
        sheet.alertStyle = .warning
        sheet.runModal()
    }
    private func confirm(_ title: String, _ detail: String) -> Bool {
        let sheet = NSAlert()
        sheet.messageText = title
        sheet.informativeText = detail
        sheet.addButton(withTitle: "Continue")
        sheet.addButton(withTitle: "Cancel")
        return sheet.runModal() == .alertFirstButtonReturn
    }
    private func run(_ executable: String, _ arguments: [String], in folder: URL? = nil,
                     visibleCommand: String? = nil, finished: ((Bool) -> Void)? = nil) {
        if busy { return }
        busy = true
        buttons.forEach { $0.isEnabled = false }
        spinner.startAnimation(nil)
        activity.stringValue = "Working…"
        log("$ " + (visibleCommand ?? ([executable] + arguments).joined(separator: " ")))

        let process = Process()
        process.executableURL = URL(fileURLWithPath: executable)
        process.arguments = arguments
        process.currentDirectoryURL = folder
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil }
            else {
                let message = String(decoding: data, as: UTF8.self)
                DispatchQueue.main.async { self?.log(message.trimmingCharacters(in: .newlines)) }
            }
        }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            var ok = false
            do {
                try process.run()
                process.waitUntilExit()
                ok = process.terminationStatus == 0
            } catch {
                let errorMessage = error.localizedDescription
                DispatchQueue.main.async { self?.log("Cannot start: " + errorMessage) }
            }
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.busy = false
                self.spinner.stopAnimation(nil)
                self.activity.stringValue = ok ? "Completed" : "Blocked or failed — inspect the log"
                self.buttons.forEach { $0.isEnabled = true }
                self.log(ok ? "✓ Success" : "Not completed; no success claimed")
                finished?(ok)
            }
        }
    }
    private func embeddedFiles() -> (URL, URL)? {
        guard let root = Bundle.main.resourceURL else {
            alert("Invalid app", "The application resources are missing.")
            return nil
        }
        let archive = root.appendingPathComponent(release)
        let checksum = root.appendingPathComponent(sums)
        if !FileManager.default.fileExists(atPath: archive.path) ||
           !FileManager.default.fileExists(atPath: checksum.path) {
            alert("Precompiled driver missing",
                  "Download the complete precompiled installer release, not a source-only build. Its signed ZIP and checksum must be bundled with the app.")
            return nil
        }
        return (archive, checksum)
    }
    @objc private func prepare() {
        guard !busy, let bundled = embeddedFiles() else { return }
        let archive = bundled.0
        guard let resources = Bundle.main.resourceURL else { return }
        let root = workspace.appendingPathComponent("packages", isDirectory: true)
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        do { try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true) }
        catch { alert("Cannot prepare folder", error.localizedDescription); return }
        // ZIP hash checked first; extract to a fresh new directory to avoid
        // Finder .DS_Store files triggering the strict package inventory.
        run("/usr/bin/shasum", ["-a", "256", "-c", sums], in: resources) { [weak self] passed in
            guard let self = self, passed else { return }
            self.run("/usr/bin/ditto", ["-x", "-k", archive.path, root.path]) { [weak self] unzipped in
                guard let self = self, unzipped else { return }
                let package = root.appendingPathComponent(self.extractedName, isDirectory: true)
                guard FileManager.default.fileExists(atPath: package.appendingPathComponent("package_manifest.py").path)
                else { self.alert("Invalid archive", "The expected compiled driver package is missing."); return }
                self.run("/usr/bin/env", ["python3", "-B", package.appendingPathComponent("package_manifest.py").path, package.path],
                         in: package) { [weak self] verified in
                    guard let self = self else { return }
                    if verified {
                        self.prepared = package
                        UserDefaults.standard.set(package.path, forKey: "preparedPackage")
                        self.preparedStatus.stringValue = "Verified SHA-256 and package manifest ✓"
                        self.filesStatus.stringValue = "Ready for diagnostic-only preflight"
                        self.log("Precompiled package prepared: " + package.path)
                    } else {
                        self.alert("Package verification refused", "Do not install this extraction. The manifest must match byte-for-byte.")
                    }
                }
            }
        }
    }
    private func requirePackage() -> URL? {
        guard let package = prepared,
              FileManager.default.fileExists(atPath: package.appendingPathComponent("install.sh").path)
        else {
            alert("Prepare first", "Click Prepare Package to verify the bundled ZIP and extract it into a clean folder.")
            return nil
        }
        return package
    }
    private func quoteShell(_ value: String) -> String {
        "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
    private func quoteAppleScript(_ value: String) -> String {
        value.replacingOccurrences(of: "\\", with: "\\\\")
             .replacingOccurrences(of: "\"", with: "\\\"")
             .replacingOccurrences(of: "\n", with: "\\n")
    }
    private func check(_ flag: String, done: ((Bool) -> Void)? = nil) {
        guard let root = requirePackage() else { return }
        run("/bin/bash", ["./install.sh", flag, "--check"], in: root, finished: done)
    }
    private func guardedInstall(_ flag: String, title: String, warning: String) {
        guard let root = requirePackage() else { return }
        check(flag) { [weak self] passed in
            guard let self = self else { return }
            if !passed {
                self.alert("Preflight refused", "The existing installer rejected this state. Nothing was installed; review its error in the log.")
                return
            }
            guard self.confirm(title, warning) else { return }
            let command = "cd " + self.quoteShell(root.path)
                + " && /bin/bash ./install.sh " + self.quoteShell(flag)
            let script = "do shell script \"" + self.quoteAppleScript(command)
                + "\" with administrator privileges"
            self.run("/usr/bin/osascript", ["-e", script],
                     visibleCommand: "Request administrator approval to run install.sh " + flag) { [weak self] success in
                guard let self = self else { return }
                if success, flag == "--fresh-files" {
                    self.filesStatus.stringValue = "Files staged; native boot/Metal still require verification"
                } else if success, flag == "--windowserver" {
                    self.desktopStatus.stringValue = "Installer completed; inspect next-boot authorization and status"
                }
            }
        }
    }
    @objc private func installFiles() {
        guardedInstall("--fresh-files", title: "Stage precompiled GPU files?",
            warning: "Only for the exact HP hardware on a safe, idle diagnostic-only boot. This backs up and stages native driver files, but does NOT update your OpenCore EFI, rebuild the auxiliary kernel collection, initialize GPU queues, enable app startup or arm WindowServer. Never stage this on a working accelerated desktop.")
    }
    @objc private func enableStartup() {
        guardedInstall("--hp-native", title: "Enable guarded app-mode boot?",
            warning: "Only after matching native GPU drivers are loaded and real native compute/render plus Metal validation pass. This configures app-only startup and may require another reboot. It does not immediately enable WindowServer.")
    }
    @objc private func armDesktop() {
        guardedInstall("--windowserver", title: "Authorize guarded accelerated WindowServer?",
            warning: "Requires matching loaded drivers, successful current-boot native/Metal tests and validated framebuffer dependencies. It may stage a reboot before authorizing the next accelerated boot. Genuine GPU or display failures cancel persistence; do not bypass recovery markers.")
    }
    @objc private func verifyPrepared() {
        guard let package = requirePackage() else { return }
        run("/usr/bin/env", ["python3", "-B", package.appendingPathComponent("package_manifest.py").path, package.path], in: package)
    }
    @objc private func checkFiles() { check("--fresh-files") }
    @objc private func checkStartup() { check("--hp-native") }
    @objc private func checkDisplay() { check("--windowserver") }
    @objc private func systemStatus() {
        let command = "echo '--- HP startup status ---'; /bin/cat /Users/Shared/nullarc-hp-native-status.json 2>&1; "
            + "echo '--- Next-boot display NVRAM ---'; (/usr/sbin/nvram -p 2>&1 | /usr/bin/grep phxfb-boot) || true; "
            + "echo '--- Driver state ---'; (/usr/bin/kmutil showloaded --list-only 2>&1 | /usr/bin/grep -E 'PhxAccel|PhxBringup') || true"
        run("/bin/sh", ["-c", command], visibleCommand: "Read-only current driver status")
    }
    @objc private func showPackage() {
        if let folder = prepared?.deletingLastPathComponent() { NSWorkspace.shared.open(folder) }
        else { alert("Nothing prepared", "Prepare the bundled driver package first.") }
    }
    @objc private func toggleAdvanced() {
        advanced.isHidden = !advanced.isHidden
    }
}

let application = NSApplication.shared
application.setActivationPolicy(.regular)
let delegate = NullArcInstaller()
application.delegate = delegate
application.run()
