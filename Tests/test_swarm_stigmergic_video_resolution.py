#!/usr/bin/env python3
"""
tests/test_swarm_stigmergic_video_resolution.py
══════════════════════════════════════════════════════════════════════
Tests for Event 90 Neuromorphic Retina.
"""

import json
from pathlib import Path
from unittest.mock import patch

from System.swarm_stigmergic_video_resolution import SwarmStigmergicResolution

def test_calculate_and_log_frame(tmp_path):
    with patch("System.swarm_stigmergic_video_resolution.Path") as mock_path:
        mock_path.return_value = tmp_path
        
        retina = SwarmStigmergicResolution(camera_width=1920, camera_height=1080, grid_size=(22, 22))
        retina.state_dir = tmp_path
        retina.resolution_ledger = tmp_path / "stigmergic_video_resolution.jsonl"
        
        mock_payload = [{"cell": [10, 11], "val": 0.8}, {"cell": [10, 12], "val": 0.9}]
        
        result = retina.calculate_and_log_frame(
            frame_id=1, 
            active_cells=15, 
            unified_field_payload=mock_payload
        )
        
        assert result["total_stig_cells"] == 484
        assert result["salience_density"] == round(15 / 484, 4)
        assert result["active_salient_cells"] == 15
        
        # Verify it was written to ledger
        assert retina.resolution_ledger.exists()
        lines = retina.resolution_ledger.read_text().strip().split("\n")
        assert len(lines) == 1
        
        row = json.loads(lines[0])
        assert row["frame_id"] == 1
        assert "salience_density" in row
