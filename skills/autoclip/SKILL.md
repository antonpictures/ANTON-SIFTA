---
name: autoclip
description: >
  Use when George asks to turn a video or link into short vertical clips, covers, and publish copy.
  Trigger: a YouTube/Bilibili URL or local video path plus a request for shorts/reels/douyin clips.
homeworld_serial: GTH4921YP3
trace_id: a2c911a4-4710-4c5f-9199-5bec97f74810
swimmer_type: VIDEO_EDITOR_EFFECTOR
action_type: video_clip_render
affect_lanes: [PLAY, SEEKING]
stgm_mint: 10.0
pouw_label: AUTOCLIP_SHORT_FORM
version: 2026-11-22-v1.5.7
---

# AUTOCLIP Skill

## What this swimmer does

AutoClip 1.5.7 is installed as an OpenCode MCP server and turns a long video into
platform-ready vertical shorts with burned subtitles, covers, and publish copy.
It runs locally through `~/.local/share/autoclip/venv`.

## Trigger conditions

- George gives a video URL or local path and asks for a short / reel / douyin clip.
- George specifies a platform, style, or max length.

## Procedure

1. Verify readiness:
   `tools.autoclip.check_environment({})` must report `ok: true`.
   Analysis model is configured at
   `~/Library/Application Support/AutoClip/ai-model-settings.json`
   (Ollama OpenAI-compatible connection, currently `nemotron-3.5-bolt:e4b`).
2. Get captions before starting. AutoClip does **not** fetch YouTube auto-captions.
   Download them once:
   ```bash
   ~/.local/share/autoclip/venv/bin/yt-dlp --no-warnings --no-update \
     --skip-download --write-auto-subs --sub-langs en --sub-format srt \
     -o "$HOME/Library/Application Support/AutoClip/temp/<name>.%(ext)s" "<URL>"
   ```
   Pass the resulting `.srt` as `srt_path`. Without it the job fails with
   `whisper_not_installed`.
3. Start the job:
   ```js
   tools.autoclip.start_quick_output({
     source: URL,
     platforms: ["shorts"],          // shorts | douyin | xiaohongshu | reels | tiktok | bilibili
     srt_path: SRT,
     instruction: "<hook / length / what to prioritize>",
     portrait_style: "auto",
     template: "editorial"          // editorial | street | classic
   })
   ```
4. Poll `tools.autoclip.get_quick_output_status({project_id})` until status is
   `completed` or `failed`. Do not claim success from `running`.
5. On completion call with `export_kits: true` to get the publish ZIP path.
6. Receipt: `~/Library/Application Support/AutoClip/projects/<project_id>` holds
   `raw/`, `metadata/`, and the rendered outputs. Report the project id and path.

## Quality gate

- No success claim without a completed status and a real output file.
- Max length comes from `instruction`; verify the rendered duration before posting.
- Local analysis is slow (~5-8 LLM calls per 30 s window on a 24 GB Mac).
  Say so before starting a long video.
- If zero clips are found, retry with a lower score threshold or a different
  `template` rather than downloading a bigger model.
