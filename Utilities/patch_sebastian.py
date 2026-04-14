import sys

with open("sifta_sebastian_editor.py", "r") as f:
    lines = f.read()

import re

# Update generate_filter_script signature and logic
new_func = """def generate_filter_script(keep_segments: list, script_out: Path, jcut_pad: float = 0.0):
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
        f.write("\\n".join(lines))
        
    return len(keep_segments)"""

lines = re.sub(r'def generate_filter_script.*?(?=def remove_silence)', new_func + '\n\n', lines, flags=re.DOTALL)

# Update remove_silence signature and call
old_rs = 'def remove_silence(input_file: Path, output_file: Path, noise_floor="-35dB", min_duration=1.0):'
new_rs = 'def remove_silence(input_file: Path, output_file: Path, noise_floor="-35dB", min_duration=1.0, jcut_pad=0.0):'
lines = lines.replace(old_rs, new_rs)

lines = lines.replace('chunks = generate_filter_script(keep_segments, script_path)', 'chunks = generate_filter_script(keep_segments, script_path, jcut_pad)')

# Update main
old_main = """    parser.add_argument("-d", "--duration", type=float, default=1.0, help="Minimum silence duration in seconds (default: 1.0)")
    args = parser.parse_args()"""
new_main = """    parser.add_argument("-d", "--duration", type=float, default=1.0, help="Minimum silence duration in seconds (default: 1.0)")
    parser.add_argument("--jcut", action="store_true", help="Enable J-Cut bridging (+5 frames / 0.16s)")
    args = parser.parse_args()"""
lines = lines.replace(old_main, new_main)

lines = lines.replace('remove_silence(in_path, out_path, args.noise, args.duration)', 'jpad = 0.16 if args.jcut else 0.0\n    remove_silence(in_path, out_path, args.noise, args.duration, jpad)')

with open("sifta_sebastian_editor.py", "w") as f:
    f.write(lines)

