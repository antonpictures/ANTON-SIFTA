// sifta_face_detect_src.swift
// Stigmergic Face Detection Organ — AS46 directive
// Uses Apple Vision.framework (VNDetectFaceRectanglesRequest) on a
// single webcam snapshot via AVFoundation.
// Outputs one JSON line to stdout, then exits.
// Wired by AG31_ANTIGRAVITY into System/swarm_face_detection.py.

import Foundation
import AVFoundation
import Vision
import CoreImage

// ── Output schema ─────────────────────────────────────────────────────────
struct FaceResult: Codable {
    var ts: Double
    var faces_detected: Int
    var confidence: Double        // max confidence across all faces
    var bounding_boxes: [[Double]] // [[x,y,w,h] …] normalised 0..1
    var source: String
    var error: String?
}

func emit(_ r: FaceResult) {
    let enc = JSONEncoder()
    enc.outputFormatting = []
    if let data = try? enc.encode(r),
       let line = String(data: data, encoding: .utf8) {
        print(line)
    }
    exit(0)
}

// ── Webcam single-frame capture ────────────────────────────────────────────
let semaphore = DispatchSemaphore(value: 0)
let ts = Date().timeIntervalSince1970

class FrameCaptor: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    let session = AVCaptureSession()
    var fired = false

    func start() {
        session.sessionPreset = .vga640x480

        guard let device = AVCaptureDevice.default(
            .builtInWideAngleCamera, for: .video, position: .front
        ) ?? AVCaptureDevice.default(for: .video) else {
            let r = FaceResult(ts: ts, faces_detected: 0, confidence: 0,
                               bounding_boxes: [], source: "webcam",
                               error: "no_camera_device")
            emit(r)
            return
        }

        guard let input = try? AVCaptureDeviceInput(device: device) else {
            let r = FaceResult(ts: ts, faces_detected: 0, confidence: 0,
                               bounding_boxes: [], source: "webcam",
                               error: "camera_input_failed")
            emit(r)
            return
        }

        let output = AVCaptureVideoDataOutput()
        output.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String:
                kCVPixelFormatType_32BGRA
        ]
        let queue = DispatchQueue(label: "sifta.facedetect")
        output.setSampleBufferDelegate(self, queue: queue)
        output.alwaysDiscardsLateVideoFrames = true

        session.addInput(input)
        session.addOutput(output)
        session.startRunning()
    }

    func captureOutput(_ output: AVCaptureOutput,
                       didOutput sampleBuffer: CMSampleBuffer,
                       from connection: AVCaptureConnection) {
        guard !fired else { return }
        fired = true
        session.stopRunning()

        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else {
            let r = FaceResult(ts: ts, faces_detected: 0, confidence: 0,
                               bounding_boxes: [], source: "webcam",
                               error: "pixel_buffer_nil")
            emit(r)
            return
        }

        // ── Vision face detection ──────────────────────────────────────────
        let req = VNDetectFaceRectanglesRequest { req, err in
            if let err = err {
                let r = FaceResult(ts: ts, faces_detected: 0, confidence: 0,
                                   bounding_boxes: [], source: "webcam",
                                   error: err.localizedDescription)
                emit(r)
                return
            }
            let obs = req.results as? [VNFaceObservation] ?? []
            var boxes: [[Double]] = []
            var maxConf = 0.0
            for o in obs {
                let b = o.boundingBox   // normalised, origin = bottom-left
                boxes.append([
                    Double(b.minX), Double(b.minY),
                    Double(b.width), Double(b.height)
                ])
                maxConf = max(maxConf, Double(o.confidence))
            }
            let r = FaceResult(ts: ts,
                               faces_detected: obs.count,
                               confidence: maxConf,
                               bounding_boxes: boxes,
                               source: "webcam",
                               error: nil)
            emit(r)
        }
        req.revision = VNDetectFaceRectanglesRequestRevision3

        let handler = VNImageRequestHandler(
            cvPixelBuffer: pixelBuffer,
            orientation: .up,
            options: [:]
        )
        do {
            try handler.perform([req])
        } catch {
            let r = FaceResult(ts: ts, faces_detected: 0, confidence: 0,
                               bounding_boxes: [], source: "webcam",
                               error: error.localizedDescription)
            emit(r)
        }
        semaphore.signal()
    }
}

let captor = FrameCaptor()
captor.start()

// Timeout safety — if camera never fires (TCC denial etc.), bail after 4s
DispatchQueue.global().asyncAfter(deadline: .now() + 4.0) {
    if !captor.fired {
        let r = FaceResult(ts: ts, faces_detected: 0, confidence: 0,
                           bounding_boxes: [], source: "webcam",
                           error: "timeout_tcc_or_no_camera")
        emit(r)
    }
}

semaphore.wait()
