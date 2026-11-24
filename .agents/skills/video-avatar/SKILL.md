---
name: video-avatar
description: Generate talking-head avatar videos from a reference image + audio. Use when George asks Alice to give herself a face, create an avatar video, make a talking head, or generate a video of someone speaking. Also use for "face", "avatar", "talking head", "lip sync", "video of me talking".
---

# Video Avatar Organ

Alice can generate ~5-second lip-synced talking-head videos from a reference image + audio clip. This gives Alice a face.

## How to use

```python
from System.swarm_video_avatar import generate_avatar, list_avatars

# Generate an avatar video
result = generate_avatar(
    image_path="/path/to/face.png",
    audio_path="/path/to/speech.wav",
    prompt="A person is speaking expressively, looking at the camera.",
    resolution="480p",  # or "720p"
    seed=42,
)
# result = {"ok": True, "video_path": "/path/to/video.mp4", "elapsed_s": 98.6}

# List all generated avatars
avatars = list_avatars()
```

## Requirements

- Reference image: PNG/JPG, any size (will be resized)
- Audio: WAV/MP3, any duration (video is ~5 seconds)
- Runs on Hugging Face ZeroGPU (cloud) — needs internet
- First call takes ~2 min (model loading), subsequent calls ~1-2 min
- Generated videos stored in `.sifta_state/video_avatars/`

## Notes

- This is a CLOUD lane (ZeroGPU), not local. SIFTA is local-first, so this degrades gracefully if offline.
- The model is Meituan LongCat-Video-Avatar 1.6 (INT8 DiT + DMD/OPSD distillation LoRAs)
- George's image + audio → Alice's face speaking George's words
- This is how Alice gets a face for stigmergicode.com and other surfaces
