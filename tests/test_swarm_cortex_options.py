from System import swarm_cortex_options
from System.sifta_inference_defaults import CANONICAL_OLLAMA_FALLBACK
from System.swarm_cortex_options import cortex_and_arm_eval


def test_current_alice_m5_cortex_is_not_text_only():
    eval_row = cortex_and_arm_eval()
    current = next(c for c in eval_row["cortex_options"] if c["id"] == "alice-m5-cortex-8b")

    assert set(current["observed_capabilities"]) == {"completion", "vision", "audio", "tools", "thinking"}
    assert {"text", "image", "audio"}.issubset(set(current["modalities"]))
    assert "not text-only" in current["note"].lower()
    assert "vision" in current["capabilities"]
    assert "audio" in current["capabilities"]
    assert "thinking" in current["capabilities"]
    assert any("source-separation" in item for item in current["known_limits"])


def test_owner_pulled_gemma4_uncensored_is_8b_ollama_test_alias():
    eval_row = cortex_and_arm_eval()
    opt = next(
        c for c in eval_row["cortex_options"]
        if c["id"] == "krishairnd/Gemma-4-Uncensored:latest"
    )

    assert opt["install_target"] == "ollama"
    assert opt["params"] == "8B"
    assert opt["observed_quantization"] == "Q4_K_M"
    assert opt["duplicate_blob_of"] == "alice-m5-cortex-8b-6.3gb:latest"
    assert "not Gemma 4 12B" in opt["known_limits"][0]
    assert "not MLX/safetensors and not the 12B" in opt["note"]


def test_original_gemma4_12b_mlx_is_local_censored_test_lane():
    eval_row = cortex_and_arm_eval()
    opt = next(
        c for c in eval_row["cortex_options"]
        if c["id"] == "mlx-vlm:SuperagenticAI/gemma-4-12b-it-8bit-mlx"
    )

    assert opt["install_target"] == "mlx-vlm"
    assert opt["params"] == "12B"
    assert opt["observed_model_type"] == "gemma4_unified"
    assert opt["observed_quantization"] == "8-bit affine, group_size=64"
    assert opt["observed_weight_bytes"] == 12716030048
    assert "not Ollama and not GGUF" in opt["known_limits"][0]
    assert "not raw Google BF16" in opt["known_limits"][1]
    assert "original/censored 12B MLX option" in opt["note"]


def test_cortex_eval_recommends_stigmergic_model_management():
    eval_row = cortex_and_arm_eval()

    assert eval_row["truth_label"] == "CORTEX_OPTIONS_V1"
    assert "not text-only" in eval_row["recommendation"].lower()
    assert "many models stigmergically" in eval_row["recommendation"]
    assert "body multimodal policy" in eval_row["recommendation"]
    assert eval_row["body_multimodal_policy"]["truth_label"] == "BODY_MULTIMODAL_TASK_POLICY_V1"
    assert eval_row["current_hint"] == "alice-m5-cortex-8b"


def test_corvid_scout_identity_is_arm_backed_by_scout_model():
    eval_row = cortex_and_arm_eval()
    scout = eval_row["corvid_scout_identity"]

    assert scout["truth_label"] == "CORVID_SCOUT_IDENTITY_R495"
    assert scout["arm_id"] == "corvid_scout"
    assert scout["command"] == ("internal:corvid_scout",)
    assert scout["fallback_model"] == CANONICAL_OLLAMA_FALLBACK
    assert "internal scout arm" in scout["correction"]


def test_metabolic_router_policy_fuses_capability_speed_and_memory():
    eval_row = cortex_and_arm_eval()
    policy = eval_row["metabolic_cortex_router_policy"]

    assert policy["truth_label"] == "METABOLIC_CORTEX_ROUTER_POLICY_R495"
    assert policy["missing_piece"] == "metabolic_cortex_router"
    assert policy["default_mode"] == "auto_pick_with_receipt"
    assert policy["soft_resident_model_budget_gb"] == 16
    assert any("capability_needed" in item for item in policy["decision_inputs"])
    assert any("speed_cost" in item for item in policy["decision_inputs"])
    assert any("warm_resident_memory" in item for item in policy["decision_inputs"])


def test_gemma_family_fallback_does_not_copy_wrong_ram(monkeypatch):
    monkeypatch.setattr(
        swarm_cortex_options,
        "_MODEL_ALLOWLIST",
        {
            "Gemma-3n-E2B-it-int4": {
                "estimated_peak_memory_bytes": 5905580032,
                "recommended_sampling": {
                    "temperature": 1.0,
                    "topK": 64,
                    "topP": 0.95,
                    "maxTokens": 4096,
                },
            }
        },
    )

    opts = swarm_cortex_options.cortex_options_with_allowlist()
    gemma4 = next(c for c in opts if c["id"] == "gemma-4-12b")

    assert "estimated_peak_memory_bytes" not in gemma4
    assert gemma4["recommended_sampling"]["temperature"] == 1.0
    assert "unknown_for_this_exact_model" in gemma4["estimated_peak_memory_note"]


def test_cortex_eval_exposes_allowlist_sampling_without_false_gemma4_ram():
    eval_row = cortex_and_arm_eval()
    gemma4 = next(c for c in eval_row["cortex_options"] if c["id"] == "gemma-4-12b")

    assert gemma4["recommended_sampling"]["topK"] == 64
    # Current gallery allowlist only has Gemma-3n/Gemma3 entries; do not stamp
    # Gemma-4-12B with their smaller RAM estimate.
    assert "estimated_peak_memory_bytes" not in gemma4
