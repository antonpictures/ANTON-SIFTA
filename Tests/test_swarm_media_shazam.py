import json
from pathlib import Path

from System.swarm_media_shazam import (
    TRUTH_LABEL,
    collect_media_evidence,
    format_guess_for_prompt,
    guess_media_identity,
    observe_current_media,
    youtube_categories,
)


def test_youtube_categories_include_active_and_legacy_catalog():
    cats = youtube_categories(include_legacy=True)
    names = {c["name"] for c in cats}
    active = {c["name"] for c in youtube_categories(include_legacy=False)}

    assert "Film & Animation" in active
    assert "News & Politics" in active
    assert "Science & Technology" in active
    assert "Trailers" in names
    assert len(cats) >= 25


def test_snatch_receipts_guess_film_clip_and_known_work():
    evidence = [
        {
            "source": "youtube_watch_memory",
            "title": "Snatch - Best of Brick top ( + deleted scene)",
            "content_category": "Film & Animation",
            "reality_frame": "FICTIONAL_MEDIA_CLIP",
            "director": "Guy Ritchie",
            "source_work": "Snatch",
            "page_context": "signals=brick,fighter,gangster,scene,clip",
        }
    ]

    guess = guess_media_identity(evidence, now=1000.0)

    assert guess["truth_label"] == TRUTH_LABEL
    assert guess["primary_category"] == "Film & Animation"
    assert guess["source_type"] == "movie_or_fiction_clip"
    assert guess["source_work"] == "Snatch"
    assert guess["director"] == "Guy Ritchie"
    assert guess["confidence"] > 0.5


def test_jensen_nvidia_receipts_guess_science_technology():
    evidence = [
        {
            "source": "media_ingress_gate",
            "title": "Jensen Huang interview on AI factories and GPUs",
            "text_preview": "NVIDIA CUDA GPU supercomputer TSMC compute scaling tokens per watt AI factory",
            "focus_preview": "youtube keynote interview",
        }
    ]

    guess = guess_media_identity(evidence, now=1000.0)

    assert guess["primary_category"] == "Science & Technology"
    assert guess["source_type"] == "tech_interview"
    assert "nvidia" in guess["evidence_terms"]


def test_news_network_receipts_guess_news_politics():
    evidence = [
        {
            "source": "youtube_context",
            "title": "CNN Breaking News: election and politics update",
            "channel": "CNN",
            "caption_excerpt": "breaking news politics election campaign congress",
        }
    ]

    guess = guess_media_identity(evidence, now=1000.0)

    assert guess["primary_category"] == "News & Politics"
    assert guess["source_type"] == "news_network"


def test_shazam_self_feedback_does_not_turn_science_video_into_gaming():
    evidence = [
        *(
            {
                "source": "acoustic_scene_classifier",
                "scene": "GAMING",
                "confidence": 0.31,
            }
            for _ in range(24)
        ),
        {
            "source": "youtube_context_latest",
            "title": "He Cracked Reality on Live TV... and a Parallel Universe Appeared - YouTube",
            "url": "https://www.youtube.com/watch?v=4tt5iXPLEqo",
        }
    ]
    for _ in range(24):
        evidence.append(
            {
                "source": "media_ingress_gate",
                "focus_preview": (
                    "George has 'SIFTA Media Shazam' open. Active tab: Co-watch guess. "
                    "Selected: He Cracked Reality on Live TV... and a Parallel Universe Appeared - YouTube. "
                    "Context: category=Gaming; conf=0.98; acoustic_scene=UNKNOWN(32%); source=gaming video. "
                    "primary_category: Gaming confidence: 0.98 acoustic_scene: UNKNOWN"
                ),
                "text_preview": (
                    "We have all heard about parallel universe alternatives. These ideas were "
                    "science fiction, physics, consciousness, perception, and experiments."
                ),
            }
        )
    evidence.append(
        {
            "source": "acoustic_scene_classifier",
            "scene": "UNKNOWN",
            "confidence": 0.31,
            "scores": {"GAMING": 0.31, "CINEMATIC": 0.13},
        }
    )

    guess = guess_media_identity(evidence, now=1000.0)

    assert guess["primary_category"] == "Science & Technology"
    assert guess["source_type"] == "science_documentary"
    assert guess["acoustic_scene"] == "UNKNOWN"
    assert guess["category_candidates"][0]["name"] != "Gaming"


def test_goodfellas_self_feedback_does_not_turn_movie_into_science():
    evidence = [
        {
            "source": "media_ingress_gate",
            "focus_preview": (
                "SIFTA Media Shazam Science & Technology "
                "source: technology interview / keynote | acoustic: receipts: 71 rows | "
                "title: Goodfellas - Don't Buy Anything - YouTube "
                "Evidence terms: don't, buy, anything, goodfellas, dialogue, you, "
                "sifta, empty, captions, fictional, selected, active, focus, unknown"
            ),
            "text_preview": (
                "Goodfellas - Don't Buy Anything movie scene playing from the computer speakers"
            ),
        },
        {
            "source": "youtube_context_latest",
            "title": "Goodfellas - Don't Buy Anything - YouTube",
            "page_context": (
                "movie scene playing from the computer speakers transcript Jimmy "
                "what did I tell you don't buy anything"
            ),
        },
    ]

    guess = guess_media_identity(evidence, now=1000.0)

    assert guess["primary_category"] == "Film & Animation"
    assert guess["source_type"] == "movie_or_fiction_clip"
    assert guess["source_work"] == "Goodfellas"
    assert guess["director"] == "Martin Scorsese"
    assert guess["category_candidates"][0]["name"] != "Science & Technology"


def test_acoustic_scene_receipts_narrow_category_before_text_guess():
    evidence = [
        {
            "source": "acoustic_scene_classifier",
            "scene": "NEWS",
            "confidence": 0.84,
            "scores": {"NEWS": 0.84, "CINEMATIC": 0.10},
        }
    ]

    guess = guess_media_identity(evidence, now=1000.0)

    assert guess["primary_category"] == "News & Politics"
    assert guess["source_type"] == "news_network"
    assert guess["acoustic_scene"] == "NEWS"
    assert guess["acoustic_scene_confidence"] == 0.84


def test_collect_and_observe_write_receipt(tmp_path: Path):
    (tmp_path / "youtube_context.jsonl").write_text(
        json.dumps(
            {
                "ts": 1000.0,
                "title": "Snatch - Best of Brick top",
                "content_category": "Film & Animation",
                "reality_frame": "FICTIONAL_MEDIA_CLIP",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    evidence = collect_media_evidence(state_dir=tmp_path, now=1005.0, window_s=60.0)
    assert len(evidence) == 1

    guess = observe_current_media(state_dir=tmp_path, now=1005.0, window_s=60.0, write=True)
    assert guess["primary_category"] == "Film & Animation"

    ledger = tmp_path / "media_shazam_guesses.jsonl"
    latest = tmp_path / "media_shazam_latest.json"
    assert ledger.exists()
    assert latest.exists()
    saved = json.loads(ledger.read_text(encoding="utf-8").splitlines()[-1])
    assert saved["truth_label"] == TRUTH_LABEL
    assert "media_guess=Film & Animation" in format_guess_for_prompt(saved)


def test_collect_evidence_includes_acoustic_scene_rows(tmp_path: Path):
    (tmp_path / "acoustic_scene_classifications.jsonl").write_text(
        json.dumps(
            {
                "ts": 1000.0,
                "scene": "CINEMATIC",
                "confidence": 0.72,
                "scores": {"CINEMATIC": 0.72},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    evidence = collect_media_evidence(state_dir=tmp_path, now=1005.0, window_s=60.0)
    guess = guess_media_identity(evidence, now=1005.0)

    assert evidence[0]["source"] == "acoustic_scene_classifier"
    assert guess["primary_category"] == "Film & Animation"
    assert guess["source_type"] == "movie_or_fiction_clip"


def test_no_recent_media_evidence_is_honest(tmp_path: Path):
    guess = observe_current_media(state_dir=tmp_path, now=1000.0, write=False)

    assert guess["status"] == "no_recent_media_evidence"
    assert guess["primary_category"] == ""
    assert guess["confidence"] == 0.0
