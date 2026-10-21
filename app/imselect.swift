// orca-dash-im: macOS 키보드 입력 소스를 조회·전환하는 보조 도구.
//
//   orca-dash-im                 현재 입력 소스 ID 출력
//   orca-dash-im <source-id> [wait_ms]   해당 입력 소스로 전환 (기본 wait 150ms)
//
// 한글·일본어·중국어 같은 입력기(IM)로의 전환은 TISSelectInputSource 만으로는 메뉴바 아이콘만 바뀌고
// 실제 적용되지 않는 macOS 버그가 있다. macism(https://github.com/laishulu/macism)과 같은 방식으로,
// 전환 직후 아주 작은 창을 잠깐 띄워 포커스를 가져갔다 돌려주면 적용된다. 인터페이스는 macism 과 같다.
import Cocoa
import Carbon

func prop(_ src: TISInputSource, _ key: CFString) -> AnyObject? {
    guard let p = TISGetInputSourceProperty(src, key) else { return nil }
    return Unmanaged<AnyObject>.fromOpaque(p).takeUnretainedValue()
}
func sourceID(_ src: TISInputSource) -> String { (prop(src, kTISPropertyInputSourceID) as? String) ?? "" }
func isCJKV(_ src: TISInputSource) -> Bool {
    guard let langs = prop(src, kTISPropertyInputSourceLanguages) as? [String], let l = langs.first else { return false }
    return l == "ko" || l == "ja" || l == "vi" || l.hasPrefix("zh")
}

let args = CommandLine.arguments.filter { !$0.hasPrefix("--") }
if CommandLine.arguments.contains("--version") { print("orca-dash-im 1.0"); exit(0) }
if args.count == 1 {
    print(sourceID(TISCopyCurrentKeyboardInputSource().takeRetainedValue()))
    exit(0)
}
let target = args[1]
let waitMs = args.count >= 3 ? (Int(args[2]) ?? 150) : 150
let list = TISCreateInputSourceList(nil, false).takeRetainedValue() as! [TISInputSource]
guard let dst = list.first(where: { sourceID($0) == target && (prop($0, kTISPropertyInputSourceIsSelectCapable) as? Bool ?? false) }) else {
    FileHandle.standardError.write("입력 소스를 찾을 수 없음: \(target)\n".data(using: .utf8)!)
    exit(1)
}
let current = TISCopyCurrentKeyboardInputSource().takeRetainedValue()
if sourceID(current) == target { exit(0) }
let status = TISSelectInputSource(dst)
if status != noErr { FileHandle.standardError.write("전환 실패 (\(status))\n".data(using: .utf8)!); exit(2) }
if !isCJKV(dst) || waitMs == 0 { exit(0) }

// 임시 창으로 포커스를 잠깐 가져가 전환을 확정시킨다.
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
if let screen = NSScreen.main {
    let r = screen.visibleFrame
    let w = NSWindow(contentRect: NSRect(x: r.maxX - 11, y: r.minY + 8, width: 3, height: 3),
                     styleMask: [.titled], backing: .buffered, defer: false)
    w.isOpaque = true
    w.backgroundColor = NSColor.windowBackgroundColor
    w.titlebarAppearsTransparent = true
    w.level = .screenSaver
    w.collectionBehavior = [.canJoinAllSpaces, .stationary]
    w.makeKeyAndOrderFront(nil)
}
app.activate(ignoringOtherApps: true)
DispatchQueue.main.asyncAfter(deadline: .now() + Double(waitMs) / 1000.0) {
    if ProcessInfo.processInfo.environment["ORCA_DASH_IM_DEBUG"] != nil {
        let now = sourceID(TISCopyCurrentKeyboardInputSource().takeRetainedValue())
        FileHandle.standardError.write("debug: active=\(app.isActive) key=\(app.keyWindow != nil) now=\(now)\n".data(using: .utf8)!)
    }
    app.terminate(nil)
}
app.run()
