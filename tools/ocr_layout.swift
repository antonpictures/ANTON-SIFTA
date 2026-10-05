// Read text out of an image, with vertical positions, so a screenshot's layout survives.
// macOS Vision; no Python dependency. Built by tools/ocr_layout.sh.
import Foundation
import Vision
import AppKit

let path = CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : ""
guard !path.isEmpty, let img = NSImage(contentsOfFile: path),
      let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("usage: ocr_layout <image>\n".data(using: .utf8)!)
    exit(2)
}
let H = Double(cg.height)
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = true
try? VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
var rows: [(Double, Double, String)] = []
for obs in (req.results ?? []) {
    guard let c = obs.topCandidates(1).first else { continue }
    let b = obs.boundingBox
    rows.append((1.0 - Double(b.origin.y) - Double(b.height), Double(b.origin.x), c.string))
}
rows.sort { $0.0 == $1.0 ? $0.1 < $1.1 : $0.0 < $1.0 }
print("image \(cg.width)x\(cg.height) — \(rows.count) text lines:")
for r in rows { print(String(format: "y=%4d x=%4d | %@", Int(r.0 * H), Int(r.1 * Double(cg.width)), r.2)) }
