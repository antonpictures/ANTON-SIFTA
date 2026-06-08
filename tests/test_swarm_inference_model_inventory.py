from __future__ import annotations


def test_inventory_scans_gguf_and_safetensors(tmp_path):
    from System.swarm_inference_model_inventory import (
        format_inventory_label,
        inventory_detail_text,
        list_inference_model_inventory,
    )

    gguf = tmp_path / "gemma-4-12b-it-UD-Q4_K_XL.gguf"
    gguf.write_bytes(b"gguf")
    mlx_dir = tmp_path / "gemma-4-e2b-it"
    mlx_dir.mkdir()
    safetensors = mlx_dir / "model.safetensors"
    safetensors.write_bytes(b"safe")
    (mlx_dir / "config.json").write_text("{}", encoding="utf-8")
    no_exist_dir = tmp_path / "models--Qwen--Qwen2-VL-2B-Instruct" / ".no_exist" / "deadbeef"
    no_exist_dir.mkdir(parents=True)
    (no_exist_dir / "model.safetensors").write_bytes(b"not-real")

    rows = list_inference_model_inventory(roots=[tmp_path], include_ollama=False)
    by_name = {row["id"]: row for row in rows}
    safetensor_row = next(row for row in rows if row["backend"] == "mlx_safetensors")

    assert by_name[gguf.name]["backend"] == "gguf"
    assert by_name[gguf.name]["quant"] == "UD-Q4_K_XL"
    assert not by_name[gguf.name]["selectable"]
    assert "llama.cpp" in by_name[gguf.name]["runtime"]

    assert safetensor_row["id"] == "gemma-4-e2b-it (1 safetensors)"
    assert not safetensor_row["selectable"]
    assert not safetensor_row["selectable_value"]
    assert safetensor_row["status"] == "installed_candidate"
    assert "MLX" in safetensor_row["runtime"]
    assert not any(".no_exist" in str(row.get("location")) for row in rows)

    assert "GGUF" not in format_inventory_label(safetensor_row)
    assert "candidate" in format_inventory_label(safetensor_row)
    assert "Runtime:" in inventory_detail_text(by_name[gguf.name])
    assert "not directly selectable" in inventory_detail_text(safetensor_row)


def test_runtime_nuggets_explain_distinct_layers():
    from System.swarm_inference_model_inventory import (
        gemma4_qat_candidate_table,
        inference_runtime_nuggets,
    )

    text = "\n".join(inference_runtime_nuggets()).lower()
    assert "mlx" in text
    assert "gguf" in text
    assert "vllm" in text
    assert "dynamic 2.0" in text
    assert "qat" in text

    rows = gemma4_qat_candidate_table()
    by_id = {row["id"]: row for row in rows}
    assert by_id["gemma-4-12B-it-qat-GGUF"]["memory_gb"] == 7.0
    assert by_id["gemma-4-26B-A4B-it-qat-GGUF"]["memory_gb"] == 15.0
    assert by_id["gemma-4-31B-it-qat-GGUF"]["sifta_role"].startswith("quality")
