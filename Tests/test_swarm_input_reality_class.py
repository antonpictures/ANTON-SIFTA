from System.swarm_input_reality_class import (
    InputRealityLane,
    classify_user_turn,
    format_lane_banner,
)


def test_classify_image_always_local_sensor():
    assert classify_user_turn("", has_image=True) is InputRealityLane.LOCAL_SENSOR_OR_PASTE


def test_classify_long_paste():
    body = "x" * 200
    assert classify_user_turn(body, has_image=False) is InputRealityLane.LOCAL_SENSOR_OR_PASTE


def test_classify_bracket_paste_short():
    assert classify_user_turn("[tool out]", has_image=False) is InputRealityLane.LOCAL_SENSOR_OR_PASTE


def test_classify_url_short():
    assert (
        classify_user_turn("see https://example.com", has_image=False)
        is InputRealityLane.REMOTE_URL_PRESENT
    )


def test_classify_room_speech():
    assert classify_user_turn("hi Alice", has_image=False) is InputRealityLane.SHORT_ROOM_SPEECH


def test_banner_contains_lane_token():
    b = format_lane_banner(InputRealityLane.LOCAL_SENSOR_OR_PASTE)
    assert "ingress_lane=LOCAL_SENSOR_OR_PASTE" in b
    assert "OBSERVED" in b
