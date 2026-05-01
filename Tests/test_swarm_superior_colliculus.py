import os
from pathlib import Path
from System.swarm_superior_colliculus import SuperiorColliculus

def test_superior_colliculus_spatial_rule():
    sc = SuperiorColliculus()
    # High spatial alignment (azimuths match)
    aligned = sc.integrate(visual_signal=0.2, visual_azimuth=0.5, 
                           audio_signal=0.2, audio_azimuth=0.5, time_delta_sec=0.0)
    
    # Low spatial alignment (azimuths different)
    misaligned = sc.integrate(visual_signal=0.2, visual_azimuth=0.5, 
                              audio_signal=0.2, audio_azimuth=1.5, time_delta_sec=0.0)
                              
    assert aligned["enhancement"] > misaligned["enhancement"]
    assert aligned["spatial_alignment"] == 1.0
    assert misaligned["spatial_alignment"] < 1.0

def test_superior_colliculus_temporal_rule():
    sc = SuperiorColliculus()
    # Coincident timing
    sync = sc.integrate(visual_signal=0.2, visual_azimuth=0.5, 
                        audio_signal=0.2, audio_azimuth=0.5, time_delta_sec=0.0)
    
    # Asynchronous timing
    async_dt = sc.integrate(visual_signal=0.2, visual_azimuth=0.5, 
                            audio_signal=0.2, audio_azimuth=0.5, time_delta_sec=0.5)
                            
    assert sync["enhancement"] > async_dt["enhancement"]
    assert sync["temporal_alignment"] == 1.0
    assert async_dt["temporal_alignment"] < 1.0

def test_superior_colliculus_inverse_effectiveness(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("System.swarm_superior_colliculus.STATE_DIR", tmp_path)
    monkeypatch.setattr("System.swarm_superior_colliculus.COLLICULUS_LOG", tmp_path / "sc.jsonl")
    
    sc = SuperiorColliculus()
    
    # Weak stimuli
    weak = sc.integrate(visual_signal=0.1, visual_azimuth=0.0, 
                        audio_signal=0.1, audio_azimuth=0.0, time_delta_sec=0.0)
                        
    # Strong stimuli
    strong = sc.integrate(visual_signal=0.8, visual_azimuth=0.0, 
                          audio_signal=0.8, audio_azimuth=0.0, time_delta_sec=0.0)
                          
    # Inverse effectiveness: multiplier is higher for weak stimuli
    assert weak["inverse_effectiveness"] > strong["inverse_effectiveness"]
    
    # Verify file write
    sc.append_integration(0.5, 0.0, 0.5, 0.0, 0.0)
    assert (tmp_path / "sc.jsonl").exists()
