
import Cocoa
import CoreGraphics

let options = CGWindowListOption(arrayLiteral: .excludeDesktopElements, .optionOnScreenOnly)
let windowListInfo = CGWindowListCopyWindowInfo(options, CGWindowID(0))
let infoList = windowListInfo as NSArray? as? [[String: AnyObject]]

if let topWindow = infoList?.first(where: { ($0[kCGWindowLayer as String] as? Int) == 0 && ($0[kCGWindowOwnerName as String] as? String) != "Window Server" }) {
    if let windowID = topWindow[kCGWindowNumber as String] as? Int {
        print(windowID)
    }
}
