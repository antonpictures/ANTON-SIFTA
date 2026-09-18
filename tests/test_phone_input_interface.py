from pathlib import Path


PAGE = Path(__file__).parents[1] / "System" / "sifta_robot_input.html"


def test_phone_interface_has_one_click_consent_and_compact_controls() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert 'id="enableEverything"' in html
    assert 'id="enableCamera"' not in html
    assert 'id="enableTelemetry"' not in html
    assert 'id="switchCamera"' in html
    assert 'id="intervalMinus"' in html
    assert 'id="intervalPlus"' in html
    assert 'id="cadenceValue"' in html
    assert 'id="send"' in html
    assert 'id="presenceState"' in html
    assert 'id="bootNotice"' in html
    assert 'id="eye"' in html
    assert 'Capture moment' not in html
    assert "BATCH_INTERVAL_MS=20000" in html
    assert "MIN_CADENCE_MS=5000" in html
    assert "MAX_CADENCE_MS=20000" in html
    assert "html{height:100%;overflow:hidden}" in html
    assert "body{margin:0;height:100%;overflow:hidden" in html
    assert "periodic_observation" in html
    assert "switchCamera()" in html
    assert "switchCamera(true)" in html
    assert "enableEverything()" in html
    assert "Promise.allSettled([cameraPromise,motionPromise,geoPromise])" in html
    assert "face_signal" in html
    assert "owner_presence:'unverified'" in html
    assert "noFaceStreak>=3" in html
    assert "FaceDetector" in html
    assert "activateEye(source)" in html
    assert "Live receipt accepted:" in html


def test_eye_animation_is_not_always_on() -> None:
    html = PAGE.read_text(encoding="utf-8")
    assert ".red-eye.is-live" in html
    assert "animation:real-data-pulse" in html
    assert ".red-eye{" in html
    assert "activateEye(source)" in html
