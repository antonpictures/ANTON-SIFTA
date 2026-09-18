"""Natural-language photo requests dispatch without the /create prefix.

Owner report 2026-09-18: a stigmergicode.com visitor asked "ok, create a photo
of Autumn in the park in Romania" and received a text promise instead of an
image, because intent matching required a bare leading verb.
"""
import pytest

from System.swarm_web_image_service import media_intent


@pytest.mark.parametrize(
    "text,expected",
    [
        ("ok, create a photo of Autumn in the park in Romania", "image"),
        ("Create a photo of yourself Alice", "image"),
        ("make me a picture of a red robot", "image"),
        ("draw a cat", "image"),
        ("paint a landscape", "image"),
        ("desenează o pisică", "image"),
        ("te rog, fă o poză cu toamna în parc", "image"),
        ("create a photo of a movie poster", "image"),
        ("create a video of a dog", "video"),
        ("paint a video of a dog", "video"),
        ("what is a photo?", ""),
        ("how do I create a photo?", ""),
        ("the park is nice", ""),
        ("generate a song", ""),
    ],
)
def test_media_intent_natural_language(text, expected):
    assert media_intent(text) == expected


def test_lead_filler_chains_are_stripped():
    # 'ok te rog, create ...' must still dispatch — bounded strip, no loops.
    assert media_intent("ok te rog, create a photo of a duck") == "image"


def test_quoted_video_title_stays_still():
    assert media_intent('create a photo titled "video"') == "image"
