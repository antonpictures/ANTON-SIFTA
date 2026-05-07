// sifta_face_detect_src.swift
// AG46 2026-05-07 | Covenant §7.11 | GTH4921YP3
//
// Captures ONE frame from the built-in FaceTime camera,
// runs Apple Vision VNDetectFaceRectanglesRequest (on-device, private),
// and prints ONE JSON line to stdout:
//
//   {"ts":1778000000.0,"faces_detected":1,"confidence":0.92,
//    "bounding_boxes":[[0.3,0.4,0.4,0.5]],"source":"webcam","error":null}
//
// Bounding boxes: [x, y, w, h] normalised 0-1, origin = bottom-left
// (Vision.framework convention — same as v1.0 schema)
//
// Exit codes: 0 = success, 1 = error

import AVFoundation
import CoreImage
import Foundation
import ImageIO
import Vision

// ─── JSON output ─────────────────────────────────────────────────────────────

struct FaceResult: Codable {
    var ts: Double
    var faces_detected: Int
    var confidence: Double
    var bounding_boxes: [[Double]]
    var source: String
    var frame_path: String?
    var error: String?
}

func emit(_ result: FaceResult) {
    let encoder = JSONEncoder()
    encoder.outputFormatting = []
    if let data = try? encoder.encode(result),
       let line = String(data: data, encoding: .utf8) {
        print(line)
        fflush(stdout)
    }
}

func emitError(_ reason: String) {
    emit(FaceResult(
        ts: Date().timeIntervalSince1970,
        faces_detected: 0,
        confidence: 0.0,
        bounding_boxes: [],
        source: "webcam",
        frame_path: nil,
        error: reason
    ))
    exit(1)
}

// ─── Camera check ─────────────────────────────────────────────────────────────

let authStatus = AVCaptureDevice.authorizationStatus(for: .video)
guard authStatus == .authorized else {
    emitError("camera_not_authorized: \(authStatus.rawValue)")
    fatalError()
}

// ─── Find camera device ───────────────────────────────────────────────────────

guard let device = AVCaptureDevice.default(
    .builtInWideAngleCamera, for: .video, position: .front
) ?? AVCaptureDevice.default(for: .video) else {
    emitError("no_camera_device")
    fatalError()
}

// ─── Capture session ──────────────────────────────────────────────────────────

let session       = AVCaptureSession()
session.sessionPreset = .vga640x480

guard let input = try? AVCaptureDeviceInput(device: device) else {
    emitError("cannot_create_input")
    fatalError()
}
session.addInput(input)

let output  = AVCaptureVideoDataOutput()
let queue   = DispatchQueue(label: "face.capture")
let sema    = DispatchSemaphore(value: 0)
var captured: CMSampleBuffer? = nil

class CapDelegate: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let sema: DispatchSemaphore
    var buf: CMSampleBuffer? = nil
    var done = false

    init(_ s: DispatchSemaphore) { self.sema = s }

    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        guard !done else { return }
        done = true
        buf  = sampleBuffer
        sema.signal()
    }
}

let delegate = CapDelegate(sema)
output.setSampleBufferDelegate(delegate, queue: queue)
output.alwaysDiscardsLateVideoFrames = true
session.addOutput(output)

// Start and wait for first frame (max 4 seconds)
session.startRunning()
let waitResult = sema.wait(timeout: .now() + 4.0)
session.stopRunning()

guard waitResult == .success, let buf = delegate.buf,
      let pixelBuffer = CMSampleBufferGetImageBuffer(buf) else {
    emitError("no_frame_captured")
    fatalError()
}

// ─── Vision face detection ────────────────────────────────────────────────────

let ts = Date().timeIntervalSince1970
let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
let ciContext = CIContext()
var savedFramePath: String? = nil

if let cgImage = ciContext.createCGImage(ciImage, from: ciImage.extent) {
    let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    let framesDir = root
        .appendingPathComponent(".sifta_state", isDirectory: true)
        .appendingPathComponent("owner_body_vision_frames", isDirectory: true)
    do {
        try FileManager.default.createDirectory(at: framesDir, withIntermediateDirectories: true)
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyyMMdd'T'HHmmss'Z'"
        formatter.timeZone = TimeZone(secondsFromGMT: 0)
        let stamp = formatter.string(from: Date(timeIntervalSince1970: ts))
        let filename = "\(stamp)_face_detect.png"
        let outputURL = framesDir.appendingPathComponent(filename)
        if let destination = CGImageDestinationCreateWithURL(outputURL as CFURL, "public.png" as CFString, 1, nil) {
            CGImageDestinationAddImage(destination, cgImage, nil)
            if CGImageDestinationFinalize(destination) {
                savedFramePath = outputURL.path
            }
        }
    } catch {
        // Frame saving is receipt context. Detection can still proceed.
    }
}

let request = VNDetectFaceRectanglesRequest()
let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, options: [:])

do {
    try handler.perform([request])
} catch {
    emitError("vision_error: \(error.localizedDescription)")
}

let observations = request.results ?? []
var boxes: [[Double]] = []
var maxConf = 0.0

for obs in observations {
    let bb = obs.boundingBox  // CGRect, normalised, origin = bottom-left
    boxes.append([
        Double(bb.origin.x),
        Double(bb.origin.y),
        Double(bb.width),
        Double(bb.height)
    ])
    maxConf = max(maxConf, Double(obs.confidence))
}

emit(FaceResult(
    ts: ts,
    faces_detected: observations.count,
    confidence: maxConf,
    bounding_boxes: boxes,
    source: "webcam",
    frame_path: savedFramePath,
    error: nil
))
exit(0)
