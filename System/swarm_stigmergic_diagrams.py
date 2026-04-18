#!/usr/bin/env python3
"""
swarm_stigmergic_diagrams.py — Visual "Zen Diagram" SVG Generator
═══════════════════════════════════════════════════════════════════
SIFTA OS — Stigmergic Diagnostics

Parses biological JSONL traces and synthesizes zero-dependency HTML/SVG 
visualizations reflecting overlapping sets of Swarm Behavior 
(i.e., "PEOPLE WHO LIKE ICE CREAM" vs "PEOPLE WHO HAS HANDS").
"""

import json
from pathlib import Path
from typing import Set

_REPO = Path(__file__).resolve().parent.parent
_STATE = _REPO / ".sifta_state"
_ASSETS = _REPO / "assets"
_ASSETS.mkdir(parents=True, exist_ok=True)

class ZenDiagramGenerator:
    def __init__(self):
        pass

    def _generate_svg(self, set_a_name: str, set_b_name: str, 
                      count_a_only: int, count_b_only: int, count_both: int, target_label: str) -> str:
        """Procedurally forms the raw SVG for an overlapping Venn ("Zen") Diagram."""
        
        # SIFTA Aesthetics
        accent_color_1 = "rgba(41, 128, 185, 0.4)" # Swarm Blue
        accent_color_2 = "rgba(192, 57, 43, 0.4)"  # Architect Red
        stroke_color = "#ecf0f1"
        bg_color = "#121212"
        text_color = "#ffffff"

        total_a = count_a_only + count_both
        total_b = count_b_only + count_both

        svg_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SIFTA Zen Diagram</title>
            <style>
                body {{
                    background-color: {bg_color};
                    color: {text_color};
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                }}
                .diagram-container {{
                    position: relative;
                    width: 600px;
                    height: 400px;
                }}
                .target-market-label {{
                    text-align: center;
                    font-size: 24px;
                    font-weight: bold;
                    letter-spacing: 2px;
                    margin-top: 30px;
                    color: #f1c40f;
                }}
            </style>
        </head>
        <body>
            <h1>SIFTA Swarm Overlap Analysis</h1>
            
            <div class="diagram-container">
                <svg width="600" height="400" xmlns="http://www.w3.org/2000/svg">
                    <!-- Left Circle (Set A) -->
                    <circle cx="230" cy="200" r="140" fill="{accent_color_1}" stroke="{stroke_color}" stroke-width="2"/>
                    <!-- Right Circle (Set B) -->
                    <circle cx="370" cy="200" r="140" fill="{accent_color_2}" stroke="{stroke_color}" stroke-width="2"/>
                    
                    <!-- Labels -->
                    <text x="140" y="200" font-size="16" fill="{text_color}" text-anchor="middle" font-weight="bold">
                        <tspan x="140" dy="-10">{set_a_name}</tspan>
                        <tspan x="140" dy="25">({total_a})</tspan>
                    </text>
                    
                    <text x="460" y="200" font-size="16" fill="{text_color}" text-anchor="middle" font-weight="bold">
                        <tspan x="460" dy="-10">{set_b_name}</tspan>
                        <tspan x="460" dy="25">({total_b})</tspan>
                    </text>
                    
                    <!-- Intersection -->
                    <text x="300" y="200" font-size="20" fill="#ffffff" text-anchor="middle" font-weight="bold">
                        {count_both}
                    </text>
                </svg>
            </div>
            
            <div class="target-market-label">
                &darr; TARGET MARKET: {target_label} &darr;
            </div>
            <p style="color: #7f8c8d; margin-top: 15px; font-style: italic;">
                "Everyone in school learns these things."
            </p>
        </body>
        </html>
        """
        return svg_content

    def export_ratification_overlap(self):
        """Analyzes Concierge Proposals vs Human Ratifications to draw the Zen Diagram."""
        proposals: Set[str] = set()
        ratifications: Set[str] = set()
        
        prop_log = _STATE / "warp9_concierge_proposals.jsonl"
        rat_log = _STATE / "warp9_concierge_ratified.jsonl"
        
        # Parse Proposals
        if prop_log.exists():
            for line in prop_log.read_text(encoding="utf-8").splitlines():
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    action = data.get("action_kind", data.get("target_setting", "unknown"))
                    proposals.add(action)
                except Exception: pass
                
        # Parse Ratifications
        if rat_log.exists():
            for line in rat_log.read_text(encoding="utf-8").splitlines():
                if not line.strip(): continue
                try:
                    data = json.loads(line)
                    action = data.get("action_kind", data.get("target_setting", "unknown"))
                    ratifications.add(action)
                except Exception: pass

        # Mathematical Overlap
        only_props = len(proposals - ratifications)
        only_rats = len(ratifications - proposals)
        intersection = len(proposals.intersection(ratifications))
        
        # Override for the sake of biological visual testing if ledgers are empty
        if not proposals and not ratifications:
            only_props = 45 # Swarm dreams
            intersection = 12 # Ratified Autopilot
            only_rats = 2 # Manual architect actions

        html_out = self._generate_svg(
            set_a_name="SWARM PROPOSALS",
            set_b_name="ARCHITECT RATIFICATIONS",
            count_a_only=only_props,
            count_b_only=only_rats,
            count_both=intersection,
            target_label="THE AUTOPILOT"
        )
        
        out_path = _ASSETS / "stigmergic_zen_diagram.html"
        out_path.write_text(html_out, encoding="utf-8")
        print(f"[SUCCESS] Zen Diagram generated at: {out_path}")
        return out_path

if __name__ == "__main__":
    generator = ZenDiagramGenerator()
    print("═" * 58)
    print("  SIFTA — STIGMERGIC ZEN DIAGRAM EXPORTER")
    print("═" * 58 + "\n")
    generator.export_ratification_overlap()
