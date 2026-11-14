import AppKit
import Foundation

// Lightweight AppKit front end. The existing install.sh remains the policy
// authority for package integrity, hardware checks, and safe rollback.
final class NullArcInstaller: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let summary = NSTextField(labelWithString: "Choose an extracted, verified NullArc package.")
    private let packageLabel = NSTextField(labelWithString: "Package: not selected")
    private let sourceLabel = NSTextField(labelWithString: "Source: not selected")
    private let configurationLabel = NSTextField(labelWithString: "Build configuration: not selected")
    private let output = NSTextView(frame: .zero)
    private var controls: [NSButton] = []
    private var package: URL?
    private var source: URL?
    private var configuration: URL?
    private var busy = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildWindow()
        append("NullArc Installer — experimental macOS 15 HP Radeon 760M.")
        append("Nothing is installed automatically. The existing installer enforces all GPU and WindowServer safeguards.")
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    private func label(_ field: NSTextField) {
        field.font = .systemFont(ofSize: 12)
        field.textColor = .secondaryLabelColor
        field.lineBreakMode = .byTruncatingMiddle
        field.maximumNumberOfLines = 1
    }

    private func button(_ title: String, _ selector: Selector) -> NSButton {
        let item = NSButton(title: title, target: self, action: selector)
        item.bezelStyle = .rounded
        controls.append(item)
        return item
    }

    private func row(_ views: [NSView]) -> NSStackView {
        let stack = NSStackView(views: views)
        stack.orientation = .horizontal
        stack.alignment = .centerY
        stack.spacing = 8
        return stack
    }

    private func heading(_ title: String) -> NSTextField {
        let item = NSTextField(labelWithString: title)
        item.font = .boldSystemFont(ofSize: 13)
        return item
    }

    private func buildWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 780, height: 660),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false)
        window.title = "NullArc Installer"
        window.minSize = NSSize(width: 680, height: 590)

        let content = NSView()
        window.contentView = content
        let stack = NSStackView()
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 10
        stack.translatesAutoresizingMaskIntoConstraints = false
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 20),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -20),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 18),
            stack.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -18)
        ])

        let title = NSTextField(labelWithString: "NullArc-760M")
        title.font = .boldSystemFont(ofSize: 22)
        stack.addArrangedSubview(title)
        summary.font = .systemFont(ofSize: 12)
        summary.textColor = .secondaryLabelColor
        stack.addArrangedSubview(summary)

        stack.addArrangedSubview(heading("Install a compiled, manifest-verified package"))
        stack.addArrangedSubview(row([
            button("Choose Package…", #selector(choosePackage)),
            button("Verify Package", #selector(verifyPackage)),
            button("Read Current Status", #selector(readStatus))
        ]))
        for field in [packageLabel, sourceLabel, configurationLabel] { label(field) }
        stack.addArrangedSubview(packageLabel)
        stack.addArrangedSubview(row([
            button("Check Files", #selector(checkFiles)),
            button("Install Files…", #selector(installFiles)),
            button("Check App Startup", #selector(checkStartup)),
            button("Enable App Startup…", #selector(enableStartup))
        ]))
        stack.addArrangedSubview(row([
            button("Check WindowServer", #selector(checkDisplay)),
            button("Arm WindowServer…", #selector(armDisplay))
        ]))

        stack.addArrangedSubview(heading("Optional: compile a new GPU stack from source"))
        stack.addArrangedSubview(row([
            button("Choose Source…", #selector(chooseSource)),
            button("Choose Build Config…", #selector(chooseConfiguration)),
            button("Compile GPU Stack…", #selector(compileStack))
        ]))
        stack.addArrangedSubview(sourceLabel)
        stack.addArrangedSubview(configurationLabel)

        stack.addArrangedSubview(heading("Operation log"))
        output.isEditable = false
        output.isSelectable = true
        output.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
        output.textContainerInset = NSSize(width: 8, height: 8)
        output.isVerticallyResizable = true
        output.autoresizingMask = [.width]
        let scroller = NSScrollView()
        scroller.hasVerticalScroller = true
        scroller.borderType = .bezelBorder
        scroller.documentView = output
        scroller.translatesAutoresizingMaskIntoConstraints = false
        stack.addArrangedSubview(scroller)
        NSLayoutConstraint.activate([
            scroller.widthAnchor.constraint(equalTo: stack.widthAnchor),
            scroller.heightAnchor.constraint(greaterThanOrEqualToConstant: 220)
        ])
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func append(_ line: String) {
        let text = line.hasSuffix("\n") ? line : line + "\n"
        output.textStorage?.append(NSAttributedString(string: text))
        output.scrollRangeToVisible(NSRange(location: max(0, output.string.utf16.count - 1), length: 0))
    }

    private func alert(_ title: String, _ message: String) {
        let a = NSAlert()
        a.messageText = title
        a.informativeText = message
        a.alertStyle = .warning
        a.runModal()
    }

    private func approve(_ title: String, _ message: String) -> Bool {
        let a = NSAlert()
        a.messageText = title
        a.informativeText = message
        a.alertStyle = .warning
        a.addButton(withTitle: "Continue")
        a.addButton(withTitle: "Cancel")
        return a.runModal() == .alertFirstButtonReturn
    }

    private func pickDirectory(_ completion: @escaping (URL) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        panel.begin { result in
            if result == .OK, let url = panel.url { completion(url.standardizedFileURL) }
        }
    }

    private func pickJSON(_ completion: @escaping (URL) -> Void) {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowedFileTypes = ["json"]
        panel.begin { result in
            if result == .OK, let url = panel.url { completion(url.standardizedFileURL) }
        }
    }

    private func exists(_ folder: URL, _ child: String) -> Bool {
        FileManager.default.fileExists(atPath: folder.appendingPathComponent(child).path)
    }

    @objc private func choosePackage() {
        guard !busy else { return }
        pickDirectory { [weak self] url in
            guard let self = self else { return }
            if !self.exists(url, "install.sh") || !self.exists(url, "package_manifest.py")
                || !self.exists(url, "package-manifest.json") {
                self.alert("Not a compiled NullArc package",
                           "Select the extracted release package, not the source repository or its parent folder.")
                return
            }
            self.package = url
            self.packageLabel.stringValue = "Package: " + url.path
            self.summary.stringValue = "Package selected. Verify it before any installation."
            self.append("Selected package: " + url.path)
        }
    }

    @objc private func chooseSource() {
        guard !busy else { return }
        pickDirectory { [weak self] url in
            guard let self = self else { return }
            if !self.exists(url, "tools/build_stack.py") {
                self.alert("Not a NullArc source checkout",
                           "Choose the repository folder containing tools/build_stack.py.")
                return
            }
            self.source = url
            self.sourceLabel.stringValue = "Source: " + url.path
            self.append("Selected source: " + url.path)
        }
    }

    @objc private func chooseConfiguration() {
        guard !busy else { return }
        pickJSON { [weak self] url in
            guard let self = self else { return }
            self.configuration = url
            self.configurationLabel.stringValue = "Build configuration: " + url.path
            self.append("Selected build configuration: " + url.path)
        }
    }

    private func selectedPackage() -> URL? {
        guard let root = package else {
            alert("Select a package", "Choose an extracted compiled package first.")
            return nil
        }
        return root
    }

    private func execute(_ program: String, _ arguments: [String], in directory: URL? = nil,
                         finished: ((Bool) -> Void)? = nil) {
        if busy { return }
        busy = true
        for control in controls { control.isEnabled = false }
        summary.stringValue = "Running: " + URL(fileURLWithPath: program).lastPathComponent
        append("$ " + program + " " + arguments.map { $0.hasPrefix("-e") ? "[AppleScript]" : $0 }.joined(separator: " "))

        let process = Process()
        process.executableURL = URL(fileURLWithPath: program)
        process.arguments = arguments
        process.currentDirectoryURL = directory
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty {
                handle.readabilityHandler = nil
            } else {
                let chunk = String(decoding: data, as: UTF8.self)
                DispatchQueue.main.async { self?.append(chunk.trimmingCharacters(in: .newlines)) }
            }
        }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            var succeeded = false
            do {
                try process.run()
                process.waitUntilExit()
                succeeded = process.terminationStatus == 0
            } catch {
                let description = String(describing: error)
                DispatchQueue.main.async { self?.append("Failed to start: " + description) }
            }
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.busy = false
                self.summary.stringValue = succeeded ? "Operation completed." : "Operation failed; see log."
                self.append(succeeded ? "Completed successfully." : "Exited unsuccessfully; no success assumed.")
                for control in self.controls { control.isEnabled = true }
                finished?(succeeded)
            }
        }
    }

    private func shellQuote(_ value: String) -> String {
        "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }

    private func appleScriptQuote(_ value: String) -> String {
        value.replacingOccurrences(of: "\\", with: "\\\\")
             .replacingOccurrences(of: "\"", with: "\\\"")
             .replacingOccurrences(of: "\n", with: "\\n")
    }

    private func privilegedInstall(_ root: URL, flag: String) {
        // AppleScript's standard administrator-privilege prompt; no persisted
        // credentials, authorization token, setuid binary, or custom root daemon.
        let command = "cd " + shellQuote(root.path)
            + " && /bin/bash ./install.sh " + shellQuote(flag)
        let script = "do shell script \"" + appleScriptQuote(command)
            + "\" with administrator privileges"
        append("Requesting macOS administrator authorization for " + flag + ".")
        execute("/usr/bin/osascript", ["-e", script])
    }

    private func check(_ flag: String, completion: ((Bool) -> Void)? = nil) {
        guard let root = selectedPackage() else { return }
        execute("/bin/bash", ["./install.sh", flag, "--check"], in: root, finished: completion)
    }

    private func install(_ flag: String, title: String, warning: String) {
        guard let root = selectedPackage() else { return }
        // The existing installer runs the manifest, hardware and runtime safety
        // checks again under elevation; this preflight never bypasses them.
        check(flag) { [weak self] passed in
            guard let self = self else { return }
            if !passed {
                self.alert("Preflight refused", "Inspect the log and correct the underlying condition. No privileged install was attempted.")
                return
            }
            if self.approve(title, warning) { self.privilegedInstall(root, flag: flag) }
        }
    }

    @objc private func verifyPackage() {
        guard let root = selectedPackage() else { return }
        execute("/usr/bin/env", ["python3", "-B", "package_manifest.py", root.path], in: root)
    }

    @objc private func checkFiles() { check("--fresh-files") }
    @objc private func installFiles() {
        install("--fresh-files", title: "Replace staged GPU files?",
                warning: "Only from an idle diagnostic-only firmware-framebuffer boot. This backs up installed native components and archives a recognized previous HP startup service. It does not rebuild the auxiliary kernel collection or initialize the GPU. Do not use on a working accelerated desktop.")
    }

    @objc private func checkStartup() { check("--hp-native") }
    @objc private func enableStartup() {
        install("--hp-native", title: "Enable guarded app-mode startup?",
                warning: "Requires matching loaded native drivers and verified Metal readbacks. The installer will reject unsafe or mismatched states. This does not arm accelerated WindowServer.")
    }

    @objc private func checkDisplay() { check("--windowserver") }
    @objc private func armDisplay() {
        install("--windowserver", title: "Authorize accelerated WindowServer?",
                warning: "Requires this boot's proven GPU/Metal and safe display prerequisites. The installer may stage an app-only reboot first. Genuine failures will cancel persistence and fall back to firmware display. Keep a backup EFI and recovery path.")
    }

    @objc private func readStatus() {
        let script = "echo '--- Last public HP boot status ---'; "
            + "/bin/cat /Users/Shared/nullarc-hp-native-status.json 2>&1; "
            + "echo '--- Current one-shot NVRAM ---'; "
            + "(/usr/sbin/nvram -p 2>&1 | /usr/bin/grep phxfb-boot) || true; "
            + "echo '--- Loaded driver ---'; "
            + "(/usr/bin/kmutil showloaded --list-only 2>&1 | /usr/bin/grep -E 'PhxAccel|PhxBringup') || true"
        execute("/bin/sh", ["-c", script])
    }

    @objc private func compileStack() {
        guard let root = source, let configFile = configuration else {
            alert("Build inputs required",
                  "Choose the source checkout and a JSON build configuration with the SDK, Mesa, translator, Vulkan headers, AIR runtime and other required dependencies.")
            return
        }
        do {
            let data = try Data(contentsOf: configFile)
            guard let values = try JSONSerialization.jsonObject(with: data) as? [String: String] else {
                throw NSError(domain: "NullArcInstaller", code: 1,
                              userInfo: [NSLocalizedDescriptionKey: "Build JSON must contain string keys and values."])
            }
            func expand(_ key: String) throws -> String {
                guard let value = values[key], !value.isEmpty else {
                    throw NSError(domain: "NullArcInstaller", code: 2,
                                  userInfo: [NSLocalizedDescriptionKey: "Missing build setting: " + key])
                }
                return URL(fileURLWithPath: value, relativeTo: root).standardizedFileURL.path
            }
            let version = values["min_macos"] ?? "15.0"
            guard version == "15.0" || version == "26.0" else {
                throw NSError(domain: "NullArcInstaller", code: 3,
                              userInfo: [NSLocalizedDescriptionKey: "Only 15.0 and 26.0 build targets are recognized. Tahoe remains unverified."])
            }
            let keys = ["sdk", "vulkan_headers", "translator_source", "glslang",
                        "mesa", "air_runtime", "dependency_notices"]
            var args = ["-B", "tools/build_stack.py", "--min-macos", version]
            for key in keys {
                let path = try expand(key)
                guard FileManager.default.fileExists(atPath: path) else {
                    throw NSError(domain: "NullArcInstaller", code: 4,
                                  userInfo: [NSLocalizedDescriptionKey: "Missing build dependency: " + path])
                }
                args += ["--" + key.replacingOccurrences(of: "_", with: "-"), path]
            }
            if values["mesa_build"] != nil {
                args += ["--mesa-build", try expand("mesa_build")]
            }
            let built = try expand("output")
            guard !FileManager.default.fileExists(atPath: built) else {
                throw NSError(domain: "NullArcInstaller", code: 5,
                              userInfo: [NSLocalizedDescriptionKey: "Build output already exists. Choose a new path: " + built])
            }
            args += ["--output", built]
            if !approve("Compile the full GPU stack?",
                        "This runs the project's existing build_stack.py locally with your supplied dependencies. Compilation is unprivileged and may consume substantial CPU/disk space. It does not install, load drivers or arm WindowServer. A successful build is not hardware validation.") {
                return
            }
            execute("/usr/bin/env", ["python3"] + args, in: root) { [weak self] ok in
                guard let self = self else { return }
                if ok {
                    let url = URL(fileURLWithPath: built)
                    self.package = url
                    self.packageLabel.stringValue = "Package: " + url.path
                    self.append("New package selected. Verify it, then follow the separate guarded install stages.")
                }
            }
        } catch {
            alert("Build configuration error", error.localizedDescription)
        }
    }
}

let application = NSApplication.shared
application.setActivationPolicy(.regular)
let delegate = NullArcInstaller()
application.delegate = delegate
application.run()
