import Speech
import Foundation

let semaphore = DispatchSemaphore(value: 0)
let args = CommandLine.arguments

guard args.count > 1 else {
    print("""
    {"error": "Missing file path"}
    """)
    exit(1)
}

let fileURL = URL(fileURLWithPath: args[1])

SFSpeechRecognizer.requestAuthorization { authStatus in
    guard authStatus == .authorized else {
        print("""
        {"error": "Not authorized for Speech Recognition. Check Apple Privacy settings."}
        """)
        semaphore.signal()
        return
    }
    
    if let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")) {
        let request = SFSpeechURLRecognitionRequest(url: fileURL)
        request.requiresOnDeviceRecognition = true
        request.shouldReportPartialResults = false
        
        recognizer.recognitionTask(with: request) { result, error in
            if let result = result, result.isFinal {
                let text = result.bestTranscription.formattedString
                let escapedText = text.replacingOccurrences(of: "\"", with: "\\\"").replacingOccurrences(of: "\n", with: " ")
                print("""
                {"text": "\(escapedText)"}
                """)
                semaphore.signal()
            } else if let error = error {
                // Not all errors are fatal (e.g. empty file), output gracefully
                let errorDesc = String(describing: error).replacingOccurrences(of: "\"", with: "'")
                print("""
                {"error": "\(errorDesc)"}
                """)
                semaphore.signal()
            }
        }
    } else {
        print("""
        {"error": "SFSpeechRecognizer unavailable for locale en-US"}
        """)
        semaphore.signal()
    }
}

// Timeout to prevent permanent hang
let timeoutResult = semaphore.wait(timeout: .now() + 10.0)
if timeoutResult == .timedOut {
    print("""
    {"error": "Speech transcription timed out. File was either too long or API is frozen waiting for Privacy permission."}
    """)
    exit(1)
}
