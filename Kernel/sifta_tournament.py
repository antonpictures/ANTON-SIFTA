import os
import sys
import json
import subprocess
from time import sleep
from pathlib import Path

ROUNDS_PER_LEVEL = 10
LEVELS = [1, 2, 3, 4]

def run_tournament(red_model, blue_model):
    print(f"==================================================")
    print(f"      SWARM ESPORTS TOURNAMENT REPORT")
    print(f"      {red_model} (RED) vs {blue_model} (BLUE)")
    print(f"      {ROUNDS_PER_LEVEL} Rounds per Level")
    print(f"==================================================\n")

    report = {"red_model": red_model, "blue_model": blue_model, "levels": {}, "totals": {"red_wins": 0, "blue_wins": 0, "draws": 0}}

    for level in LEVELS:
        print(f"\n[⚔️] LEVEL {level} BEGINNING...")
        level_stats = {"red_wins": 0, "blue_wins": 0, "draws": 0}
        
        for round in range(1, ROUNDS_PER_LEVEL + 1):
            print(f"  Level {level} - Round {round}/{ROUNDS_PER_LEVEL}...", end=" ", flush=True)
            
            cmd = ["python3", "-u", "sifta_arena.py", "--red", red_model, "--blue", blue_model, "--level", str(level)]
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                red_passed = False
                blue_passed = False
                
                # Parse the JSON-L stream from the match
                for line in res.stdout.split('\n'):
                    if not line: continue
                    try:
                        data = json.loads(line)
                        if data.get("type") == "result":
                            if data.get("team") == "red":
                                red_passed = data.get("passed", False)
                            elif data.get("team") == "blue":
                                blue_passed = data.get("passed", False)
                    except json.JSONDecodeError:
                        pass
                
                if red_passed and blue_passed:
                    level_stats["draws"] += 1
                    report["totals"]["draws"] += 1
                    print("DRAW (Both Passed)")
                elif red_passed:
                    level_stats["red_wins"] += 1
                    report["totals"]["red_wins"] += 1
                    print("RED WINS")
                elif blue_passed:
                    level_stats["blue_wins"] += 1
                    report["totals"]["blue_wins"] += 1
                    print("BLUE WINS")
                else:
                    level_stats["draws"] += 1
                    report["totals"]["draws"] += 1
                    print("DOUBLE KO (Both Failed)")
                    
            except subprocess.TimeoutExpired:
                print("TIMEOUT MATCH ABORTED")
                level_stats["draws"] += 1
                
        report["levels"][f"level_{level}"] = level_stats
        print(f"  Level {level} Final:")
        print(f"   - {red_model} (Red)  : {level_stats['red_wins']} wins")
        print(f"   - {blue_model} (Blue): {level_stats['blue_wins']} wins")

    print(f"\n==================================================")
    print(f"                 FINAL TOURNAMENT RESULTS")
    print(f"==================================================")
    print(f" {red_model} (RED): {report['totals']['red_wins']} Total Wins")
    print(f" {blue_model} (BLUE): {report['totals']['blue_wins']} Total Wins")
    print(f" Draws / Mutual Failures: {report['totals']['draws']}")
    
    winner = "RED" if report["totals"]["red_wins"] > report["totals"]["blue_wins"] else "BLUE" if report["totals"]["blue_wins"] > report["totals"]["red_wins"] else "TIE"
    print(f"\n OVERALL TOURNAMENT WINNER: {winner} TEAM!")
    
    Path("tournament_report.json").write_text(json.dumps(report, indent=4))
    print("\n[+] Full report saved to tournament_report.json")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--red", required=True)
    parser.add_argument("--blue", required=True)
    parser.add_argument("--rounds", type=int, default=10)
    args = parser.parse_args()
    
    ROUNDS_PER_LEVEL = args.rounds
    run_tournament(args.red, args.blue)
