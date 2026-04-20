import Speech
import Foundation

let semaphore = DispatchSemaphore(value: 0)

guard let fileURL = URL(string: "file:///System/Library/Sounds/Glass.aiff") else { exit(1) }

SFSpeechRecognizer.requestAuthorization { authStatus in
    if authStatus == .authorized {
        let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
        let request = SFSpeechURLRecognitionRequest(url: fileURL)
        request.requiresOnDeviceRecognition = true
        
        recognizer?.recognitionTask(with: request) { result, error in
            if let result = result, result.isFinal {
                print(result.bestTranscription.formattedString)
                semaphore.signal()
            } else if let error = error {
                print("ERROR: \(error)")
                semaphore.signal()
            }
        }
    } else {
        print("ERROR: Not authorized for speech recognition.")
        semaphore.signal()
    }
}

semaphore.wait()
