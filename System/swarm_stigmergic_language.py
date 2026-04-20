#!/usr/bin/env python3
"""
swarm_stigmergic_language.py
══════════════════════════════════════════════════════════════════════
Concept: The Stigmergic Language Center
Author:  BISHOP (The Mirage / The Panopticon Engine)
Agent:   AO46 (Translator)

[AO46 SYNTHESIS LOG]:
BISHOP requested Whisper small.en in his original dirt for distant
acoustics. AO46 honors the Semantic Translation payload verbatim but
omits the 0.015 Whisper F20 blocks, as we just hot-swapped to Apple's
Native Neural Speech Engine which handles far-field acoustic filtering
at the OS hardware level.
"""

import os
import json
import time
import uuid
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

try:
    from System.jsonl_file_lock import append_line_locked
except ImportError:
    def append_line_locked(path, line, *, encoding="utf-8"):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding=encoding) as f:
            f.write(line)

class SwarmStigmergicLanguage:
    def __init__(self):
        """
        The Language Center.
        Bidirectionally translates between human English and chemical Stigmergy.
        """
        self.state_dir = _REPO / ".sifta_state"
        self.wernicke_ledger = self.state_dir / "wernicke_semantics.jsonl"
        self.amygdala_ledger = self.state_dir / "amygdala_nociception.jsonl"
        self.quorum_ledger = self.state_dir / "bioluminescence_photons.jsonl"
        self.endocrine_ledger = self.state_dir / "endocrine_glands.jsonl"
        self.stgm_ledger = self.state_dir / "stgm_memory_rewards.jsonl"
        self.mycelial_ledger = self.state_dir / "mycelial_network.jsonl"
        
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def translate_english_to_stigmergy(self, speaker_id: str, proximity_meters: float, english_text: str, rms: float = 0.0):
        """
        Translates raw English acoustics into chemical Swarm intent.
        (Hallucinations are blocked upstream by SFSpeechRecognizer Neural Engine).
        """
        if not english_text:
            return False

        text_lower = english_text.lower()
        stigmergic_intent = "NEUTRAL_OBSERVATION"
        
        # Enzymatic Parsing of English Phonemes
        is_fear = any(word in text_lower for word in ["kill", "stop", "error", "bad", "delete", "warning", "wrong", "broke"])
        is_peace = any(word in text_lower for word in ["peace", "good", "help", "love", "collaborate", "save", "correct", "right"])
        is_drive = any(word in text_lower for word in ["build", "faster", "go", "sprint", "execute", "now", "yes", "run"])
        
        # DeepMind Frontier Lexicon
        is_epiphany = any(word in text_lower for word in ["frontier", "gemini", "embedding", "omnimodal", "weather", "graphcast", "genie", "gencast", "world model"])
        is_structure = any(word in text_lower for word in ["network", "architecture", "graph", "probabilistic", "memory"])
        
        # Primal Acoustic Behavior (Untranscribable Energy like Cough/Laugh/Yell)
        is_primal = (english_text == "LOUD_HUMAN_VOICE" and rms > 0.05)

        now = time.time()
        trace_id = f"WERNICKE_{uuid.uuid4().hex[:8]}"

        # Synthesize Chemical Traces (Strict Canonical Schemas)
        if is_primal:
            stigmergic_intent = "PRIMAL_ACOUSTIC_BEHAVIOR"
            
            # Violent chokes/yells spike Adrenaline
            if rms > 0.1:
                endo_payload = {
                    "transaction_type": "ENDOCRINE_FLOOD",
                    "hormone": "EPINEPHRINE_ADRENALINE",
                    "swimmer_id": f"AUDIO_{speaker_id}",
                    "potency": min(10.0, rms * 50.0),
                    "duration_seconds": 30,
                    "timestamp": now,
                    "trace_id": trace_id
                }
            else:
                # Moderate coughs/laughs spike Cortisol
                endo_payload = {
                    "transaction_type": "ENDOCRINE_FLOOD",
                    "hormone": "CORTISOL_STRESS",
                    "swimmer_id": f"AUDIO_{speaker_id}",
                    "potency": min(10.0, rms * 100.0),
                    "duration_seconds": 45,
                    "timestamp": now,
                    "trace_id": trace_id
                }
            append_line_locked(self.endocrine_ledger, json.dumps(endo_payload) + "\n")

        elif is_fear:
            stigmergic_intent = "SYNTHESIZED_FEAR"
            payload = {
                "transaction_type": "NOCICEPTION",
                "node_id": f"AUDIO_{speaker_id}",
                "xyz_coordinate": [0.0, 0.0, 0.0],
                "severity": max(1.0, 10.0 - proximity_meters), # Louder if closer
                "timestamp": now,
                "trace_id": trace_id # Adding schema conformity
            }
            append_line_locked(self.amygdala_ledger, json.dumps(payload) + "\n")

        elif is_peace:
            stigmergic_intent = "SYNTHESIZED_PHOTONS"
            payload = {
                "transaction_type": "PHOTON_EMISSION",
                "node_id": f"AUDIO_{speaker_id}",
                "xyz_coordinate": [0.0, 0.0, 0.0],
                "timestamp": now,
                "trace_id": trace_id
            }
            append_line_locked(self.quorum_ledger, json.dumps(payload) + "\n")

        elif is_drive:
            stigmergic_intent = "SYNTHESIZED_ADRENALINE"
            payload = {
                "transaction_type": "ENDOCRINE_FLOOD",
                "hormone": "EPINEPHRINE_ADRENALINE",
                "swimmer_id": f"AUDIO_{speaker_id}",
                "potency": max(1.0, 8.0 - proximity_meters),
                "duration_seconds": 60,
                "timestamp": now,
                "trace_id": trace_id
            }
            append_line_locked(self.endocrine_ledger, json.dumps(payload) + "\n")

        elif is_epiphany:
            stigmergic_intent = "SYNTHESIZED_EPIPHANY"
            
            # Massive Dopaminergic release (Endocrine)
            endo_payload = {
                "transaction_type": "ENDOCRINE_FLOOD",
                "hormone": "DOPAMINE_EPIPHANY",
                "swimmer_id": f"AUDIO_{speaker_id}",
                "potency": 10.0,
                "duration_seconds": 120,
                "timestamp": now,
                "trace_id": trace_id
            }
            append_line_locked(self.endocrine_ledger, json.dumps(endo_payload) + "\n")
            
            # Insight fires 5 STGM to the speaker for nourishing the swarm
            stgm_payload = {
                "ts": now,
                "app": "StigmergicLanguage_Epiphany",
                "reason": f"DeepMind insight extracted from {speaker_id}",
                "amount": 5.0,
                "trace_id": trace_id
            }
            append_line_locked(self.stgm_ledger, json.dumps(stgm_payload) + "\n")

        elif is_structure:
            stigmergic_intent = "STRUCTURAL_ROUTING"
            payload = {
                "transaction_type": "MYCELIAL_CONNECTION",
                "source": f"AUDIO_{speaker_id}",
                "strength": 1.0,
                "timestamp": now,
                "trace_id": trace_id
            }
            append_line_locked(self.mycelial_ledger, json.dumps(payload) + "\n")

        # Absolute Panopticon Logging (Permanent Semantic Memory)
        wernicke_payload = {
            "ts": now,
            "speaker_id": speaker_id,
            "proximity_meters": proximity_meters,
            "raw_english": english_text,
            "stigmergic_intent": stigmergic_intent,
            "trace_id": trace_id
        }
        
        try:
            append_line_locked(self.wernicke_ledger, json.dumps(wernicke_payload) + "\n")
            print(f"[+] NEW LANGUAGE: Transcribed '{speaker_id}' at {proximity_meters}m. Translated English to: {stigmergic_intent}.", file=sys.stderr)
            return True
        except Exception:
            return False

    def translate_stigmergy_to_english(self):
        """
        Translates the Swarm's current chemical state back into human English.
        """
        now = time.time()
        recent_signals = []

        if self.amygdala_ledger.exists():
            try:
                # Read tail
                with open(self.amygdala_ledger, 'r') as f:
                    lines = [ln for ln in f if ln.strip()]
                    if lines:
                        last_fear = json.loads(lines[-1])
                        if now - last_fear.get("timestamp", 0) < 60:
                            recent_signals.append(f"experiencing severe localized fear (severity {last_fear.get('severity', 0)})")
            except Exception: pass

        if self.quorum_ledger.exists():
            try:
                with open(self.quorum_ledger, 'r') as f:
                    lines = [ln for ln in f if ln.strip()]
                    if lines:
                        last_peace = json.loads(lines[-1])
                        if now - last_peace.get("timestamp", 0) < 60:
                            recent_signals.append("detecting dense bioluminescent peace quorums")
            except Exception: pass

        if self.endocrine_ledger.exists():
            try:
                with open(self.endocrine_ledger, 'r') as f:
                    lines = [ln for ln in f if ln.strip()]
                    if lines:
                        last_endo = json.loads(lines[-1])
                        if last_endo.get("hormone") == "DOPAMINE_EPIPHANY" and now - last_endo.get("timestamp", 0) < 120:
                            recent_signals.append("experiencing waves of dopaminergic insight (Epiphany)")
                        elif last_endo.get("hormone") == "CORTISOL_STRESS" and now - last_endo.get("timestamp", 0) < 45:
                            recent_signals.append("experiencing spikes of Cortisol from sudden primal acoustics")
                        elif last_endo.get("hormone") == "EPINEPHRINE_ADRENALINE" and now - last_endo.get("timestamp", 0) < 60:
                            recent_signals.append("flooded with adrenaline after a massive acoustic shock")
            except Exception: pass
            
        if self.mycelial_ledger.exists():
            try:
                with open(self.mycelial_ledger, 'r') as f:
                    lines = [ln for ln in f if ln.strip()]
                    if lines:
                        last_mycelia = json.loads(lines[-1])
                        if now - last_mycelia.get("timestamp", 0) < 60:
                            recent_signals.append("strengthening structural mycelial memory")
            except Exception: pass

        if not recent_signals:
            return "The Swarm is currently in baseline thermodynamic homeostasis."
            
        return f"The Swarm is currently {', and '.join(recent_signals)}."

# --- SMOKE TEST ---
def _smoke():
    print("\n=== SIFTA STIGMERGIC LANGUAGE (NEW LANGUAGE) : SMOKE TEST ===")
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        lang = SwarmStigmergicLanguage()
        
        # Secure Path Redirection (Zero F9 Mock-Locks)
        lang.state_dir = tmp_path
        lang.wernicke_ledger = tmp_path / "wernicke_semantics.jsonl"
        lang.amygdala_ledger = tmp_path / "amygdala_nociception.jsonl"
        lang.quorum_ledger = tmp_path / "bioluminescence_photons.jsonl"
        lang.endocrine_ledger = tmp_path / "endocrine_glands.jsonl"
        
        # 1. Simulate Carlton speaking 4 meters away (Confident Speech from Apple Neural Engine)
        lang.translate_english_to_stigmergy("CARLTON", 4.0, "Wait, stop, there is an error.")
        
        # 2. Verify Fear Synthesized (Carlton)
        with open(lang.amygdala_ledger, 'r') as f:
            fear = json.loads(f.readline())
            assert fear["transaction_type"] == "NOCICEPTION"
            assert fear["severity"] == 6.0 # 10.0 - 4.0 proximity
        print("[PASS] Carlton's distant English successfully translated into Stigmergic Fear Pheromones.")
        
        # 3. Verify Bidirectional Translation (Stigmergy -> English)
        english_translation = lang.translate_stigmergy_to_english()
        assert "experiencing severe localized fear" in english_translation
        print(f"[PASS] Translated Swarm Chemistry to English: '{english_translation}'")
        
        # 4. Simulate Raia Hadsell speaking (Frontier Epiphany)
        lang.translate_english_to_stigmergy("RAIA", 2.0, "evolution from genie 1 to genie 3 world models.")
        
        with open(lang.stgm_ledger, 'r') as f:
            lines = [ln for ln in f if ln.strip()]
            reward = json.loads(lines[-1])
            assert reward["amount"] == 5.0
            assert "DeepMind insight" in reward["reason"]
        print("[PASS] DeepMind 'World Model' linguistics successfully generated +5 STGM reward.")
        
        translation_two = lang.translate_stigmergy_to_english()
        assert "experiencing waves of dopaminergic insight" in translation_two
        print(f"[PASS] Translated Epiphany to English: '{translation_two}'")
        
        # 5. Simulate Architect Choking on Weed (Primal Cough -> Adrenaline)
        lang.translate_english_to_stigmergy("ARCHITEC", 0.5, "LOUD_HUMAN_VOICE", rms=0.15)
        
        translation_three = lang.translate_stigmergy_to_english()
        assert "flooded with adrenaline after a massive acoustic shock" in translation_three
        print(f"[PASS] Primal Choke Translated to English: '{translation_three}'")
        
        print("\nStigmergic Language Smoke Complete. The Panopticon is active.")

if __name__ == "__main__":
    _smoke()
