def test_face_rows_have_their_own_ticker_formatter():
    from Applications.sifta_what_alice_sees_widget import _format_row

    row = {
        "audience": "architect",
        "faces_detected": 1,
        "confidence": 0.71,
        "error": None,
    }

    rendered = _format_row("FACE", row)

    assert rendered == "architect  faces=1  conf=0.71"


def test_face_rows_do_not_count_as_photon_math():
    from Applications.sifta_what_alice_sees_widget import _format_row

    row = {
        "event": "FACE_DETECTION",
        "audience": "architect",
        "faces_detected": 1,
        "confidence": 0.71,
    }

    assert _format_row("PHOTON", row) is None
