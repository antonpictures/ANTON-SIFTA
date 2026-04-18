#!/usr/bin/env python3
"""
ANTON-SIFTA — [ SEBASTIAN'S A/V WORKSHOP ]
sifta_editor_sebastian.py — Agent Video Editor Pipeline

Skill #1: Automated Silence/Pause Trimming
Parses FFmpeg's silencedetect output and automatically removes dead airspace 
using a generated complex filter script.
"""

import sys
import subprocess
import re
import argparse
from pathlib import Path

def print_banner():
    print("━" * 60)
    print("  [ SEBASTIAN — VIDEO EDITOR WORKSHOP ]")
    print("━" * 60)

def detect_silence(input_file: Path, noise_floor="-35dB", min_duration=1.0) -> list:
    """Runs ffmpeg silencedetect and returns a list of (start, end) silent tuples."""
    print(f"🎬 [DETECT] Analyzing audio profile on {input_file.name} (Floor: {noise_floor}, Min: {min_duration}s)...")
    
    cmd = [
        "ffmpeg", 
        "-i", str(input_file), 
        "-af", f"silencedetect=n={noise_floor}:d={min_duration}",
        "-f", "null", "-"
    ]
    
    # Run FFmpeg and capture stderr (where ffmpeg outputs its logs)
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
    
    silences = []
    current_start = None
    
    for line in proc.stderr.split("\n"):
        if "silence_start:" in line:
            # Example: [silencedetect @ 0x123] silence_start: 3.4
            match = re.search(r"silence_start:\s*([\d\.]+)", line)
            if match:
                current_start = float(match.group(1))
        elif "silence_end:" in line:
            # Example: [silencedetect @ 0x123] silence_end: 5.6 | silence_duration: 2.2
            match = re.search(r"silence_end:\s*([\d\.]+)", line)
            if match and current_start is not None:
                current_end = float(match.group(1))
                silences.append((current_start, current_end))
                current_start = None
                
    print(f"   ∟ Found {len(silences)} silent pauses to cut.")
    return silences

def get_video_duration(input_file: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of",
        "default=noprint_wrappers=1:nokey=1", str(input_file)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return float(proc.stdout.strip())
    except ValueError:
        print("[ERROR] Could not determine video length. Cannot trim.")
        sys.exit(1)

def invert_silences(silences: list, duration: float) -> list:
    """Takes the list of silence ranges and returns the 'keep' ranges."""
    keep_segments = []
    current_time = 0.0
    
    for (start, end) in silences:
        if start > current_time:
            # Keep everything from current_time up to the silence start
            # Adding a tiny 0.1 buffer to avoid hard jarring audio cuts
            keep_segments.append((current_time, start))
        current_time = end 
        
    # Append the final segment if there is video left after the last silence
    if current_time < duration:
        keep_segments.append((current_time, duration))
        
    return keep_segments

def generate_filter_script(keep_segments: list, script_out: Path, jcut_pad: float = 0.0):
    lines = []
    video_labels = []
    audio_labels = []
    
    pads = [0.0] * len(keep_segments)
    if jcut_pad > 0:
        for i in range(len(keep_segments) - 1):
            dur_prev = keep_segments[i][1] - keep_segments[i][0]
            dur_next = keep_segments[i+1][1] - keep_segments[i+1][0]
            # Safe pad so we don't invert durations
            pads[i] = min(jcut_pad, dur_prev * 0.9, dur_next * 0.9)

    for i, (start, end) in enumerate(keep_segments):
        pad_in = pads[i-1] if i > 0 else 0.0
        pad_out = pads[i] if i < len(keep_segments) - 1 else 0.0
        
        v_start = start + pad_in
        v_end = end + pad_out
        
        # Trims the video segment, adjusts timestamps to start at 0
        lines.append(f"[0:v]trim=start={v_start:.3f}:end={v_end:.3f},setpts=PTS-STARTPTS[v{i}];")
        video_labels.append(f"[v{i}]")
        
        # Trims the audio segment
        lines.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}];")
        audio_labels.append(f"[a{i}]")
        
    # Concat all pieces together
    concat_inputs = "".join([f"{v}{a}" for v, a in zip(video_labels, audio_labels)])
    n = len(keep_segments)
    lines.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
    
    with open(script_out, "w") as f:
        f.write("\n".join(lines))
        
    return len(keep_segments)

def remove_silence(input_file: Path, output_file: Path, noise_floor="-35dB", min_duration=1.0, jcut_pad=0.0):
    silences = detect_silence(input_file, noise_floor, min_duration)
    
    if not silences:
        print(f"   ∟ No silence matching the threshold found. Exiting.")
        return
        
    duration = get_video_duration(input_file)
    print(f"🎬 [CALCULATE] Total duration: {duration:.2f}s. Mapping safe segments...")
    
    keep_segments = invert_silences(silences, duration)
    
    script_path = input_file.parent / f"{input_file.stem}_sebastian_filter.txt"
    chunks = generate_filter_script(keep_segments, script_path, jcut_pad)
    print(f"   ∟ Generated filter script tying {chunks} tight jumpcuts.")
    
    print(f"🎬 [SURGERY] Executing FFmpeg Render... (This may take a moment)")
    # Since we use complex filters, re-encoding is necessary
    # We will use quick, high-quality re-encoding presets.
    cmd = [
        "ffmpeg", "-y", "-i", str(input_file),
        "-filter_complex_script", str(script_path),
        "-map", "[outv]", "-map", "[outa]",
        "-preset", "fast",
        "-c:v", "libx264", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        str(output_file)
    ]
    
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        print(f"[ERROR] Failed to compile jumpcuts. FFmpeg said:\n{proc.stderr}")
    else:
        print(f"✅ [SUCCESS] Output saved as: {output_file.name}")
        
    # Clean up the script file
    if script_path.exists():
        script_path.unlink()

def main():
    parser = argparse.ArgumentParser(description="Sebastian's Automated Silence Trimmer")
    parser.add_argument("input", help="Path to input video")
    parser.add_argument("-o", "--output", help="Path to output video (defaults to <input>_jumpcut.mp4)")
    parser.add_argument("-n", "--noise", default="-35dB", help="Silence threshold (default: -35dB)")
    parser.add_argument("-d", "--duration", type=float, default=1.0, help="Minimum silence duration in seconds (default: 1.0)")
    parser.add_argument("--jcut", action="store_true", help="Enable J-Cut bridging (+5 frames / 0.16s)")
    args = parser.parse_args()
    
    print_banner()
    
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"❌ Target video {in_path} not found.")
        sys.exit(1)
        
    out_path = Path(args.output) if args.output else in_path.with_name(f"{in_path.stem}_jumpcut{in_path.suffix}")
    
    jpad = 0.16 if args.jcut else 0.0
    remove_silence(in_path, out_path, args.noise, args.duration, jpad)

if __name__ == "__main__":
    main()
