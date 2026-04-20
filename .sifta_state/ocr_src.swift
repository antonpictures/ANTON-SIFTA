
import Vision
import Foundation

guard CommandLine.arguments.count > 1 else {
    print("Usage: sifta_vision_ocr <image_path>")
    exit(1)
}

let imagePath = CommandLine.arguments[1]
let url = URL(fileURLWithPath: imagePath)

guard let handler = try? VNImageRequestHandler(url: url, options: [:]) else {
    print("Error: Could not load image.")
    exit(1)
}

let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else {
        return
    }
    for observation in observations {
        guard let topCandidate = observation.topCandidates(1).first else { continue }
        print(topCandidate.string)
    }
}
request.recognitionLevel = .accurate

do {
    try handler.perform([request])
} catch {
    print("Error: \(error)")
    exit(1)
}
