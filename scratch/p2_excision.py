import sys, os
import numpy as np
import gguf
from pathlib import Path

sys.path.insert(0, os.path.abspath('System'))
from swarm_orthogonal_abliteration import _copy_kv, _architecture, _tensor_fp32

TUNED_FILE = "/Users/ioanganton/.ollama/models/blobs/sha256-4c27e0f5b5adf02ac956c7322bd2ee7636fe3f45a8512c9aba5385242cb6e09a"
BASE_FILE = "/Users/ioanganton/.ollama/models/blobs/sha256-bb44ce787b29b8918d40d14383d5f8b10f279c19fb4d27357f78e82328f7276a"
OUT_FILE = "scratch/Gemma4_Intermediate_F16.gguf"

_FORCE_F16_INTERMEDIATE = frozenset({
    # llama-quantize aborts when converting these 4D F32 conv kernels to F16.
    # Emit them as F16 here using the native NumPy shape so GGUFWriter writes
    # the original logical shape after its dimension reversal.
    "a.conv1d.0.weight",
    "a.conv1d.1.weight",
})


def _is_surgical_target(name: str) -> bool:
    """Only text decoder blk.* attention/FFN weight tensors are surgical targets.
    Everything else is passed through byte-exact."""
    if not name.startswith("blk."):
        return False
    # Only operate on weight matrices in attention and FFN sublayers
    surgical_suffixes = (
        ".attn_k.weight", ".attn_q.weight", ".attn_v.weight", ".attn_output.weight",
        ".ffn_down.weight", ".ffn_gate.weight", ".ffn_up.weight",
    )
    return name.endswith(surgical_suffixes)


def execute_p2_surgery():
    print(f"[*] Loading Base Genome...")
    reader_base = gguf.GGUFReader(BASE_FILE)
    tensors_base = {t.name: t for t in reader_base.tensors}

    print(f"[*] Loading Tuned Genome...")
    reader_tuned = gguf.GGUFReader(TUNED_FILE)

    arch = _architecture(reader_tuned)
    writer = gguf.GGUFWriter(OUT_FILE, arch)
    _copy_kv(reader_tuned, writer)

    lmbda = 1.0
    threshold = 1e-4

    excised_count = 0
    passthrough_count = 0
    forced_f16_count = 0
    total = len(reader_tuned.tensors)

    for idx, t_tuned in enumerate(reader_tuned.tensors):
        name = t_tuned.name
        endian = reader_tuned.endianess

        if _is_surgical_target(name) and name in tensors_base:
            t_base = tensors_base[name]
            if list(t_tuned.shape) == list(t_base.shape):
                w_tuned = _tensor_fp32(t_tuned)
                w_base = _tensor_fp32(t_base)
                tau = w_tuned - w_base
                delta_mass = float(np.abs(tau).sum())

                if delta_mass > threshold:
                    w_new = w_tuned - (lmbda * tau)
                    # Rewritten surgical tensor: NumPy-native shape, no raw_shape
                    payload = np.ascontiguousarray(np.asarray(w_new, dtype=np.float16))
                    writer.add_tensor(name, payload, raw_dtype=None, tensor_endianess=endian)
                    excised_count += 1
                    if (idx+1) % 100 == 0:
                        print(f"  [+] Scalpel passed layer {idx+1}/{total} ...")
                    continue

        if name in _FORCE_F16_INTERMEDIATE:
            payload = np.ascontiguousarray(np.asarray(t_tuned.data, dtype=np.float16))
            writer.add_tensor(name, payload, raw_dtype=None, tensor_endianess=endian)
            forced_f16_count += 1
            if (idx+1) % 100 == 0:
                print(f"  [+] Scalpel passed layer {idx+1}/{total} ...")
            continue

        # Raw passthrough: preserve exact original bytes and dtype
        payload = np.ascontiguousarray(t_tuned.data).copy()
        writer.add_tensor(name, payload, raw_dtype=t_tuned.tensor_type, tensor_endianess=endian)
        passthrough_count += 1

        if (idx+1) % 100 == 0:
            print(f"  [+] Scalpel passed layer {idx+1}/{total} ...")

    print(f"\n[!] Writing Massive F16 payload to disk...")
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()

    print(f"[+] Surgery Complete. Excised {excised_count} text decoder tensors.")
    print(f"[+] Passed through {passthrough_count} tensors byte-exact.")
    print(f"[+] Forced {forced_f16_count} fragile conv tensors to F16 before quantization.")
    print(f"[+] Wrote intermediate to {OUT_FILE}")

    # ── POST-SURGERY SHAPE ASSERTION ──
    print(f"\n[*] Running shape parity assertion...")
    reader_out = gguf.GGUFReader(OUT_FILE)
    tensors_out = {t.name: t for t in reader_out.tensors}
    shape_errors = []
    for t_orig in reader_tuned.tensors:
        if t_orig.name not in tensors_out:
            shape_errors.append(f"  MISSING: {t_orig.name}")
            continue
        t_new = tensors_out[t_orig.name]
        orig_shape = [int(x) for x in t_orig.shape]
        new_shape = [int(x) for x in t_new.shape]
        if orig_shape != new_shape:
            shape_errors.append(f"  MISMATCH: {t_orig.name}: original={orig_shape} new={new_shape}")

    if shape_errors:
        print(f"[FAIL] Shape parity check found {len(shape_errors)} errors:")
        for e in shape_errors:
            print(e)
        sys.exit(1)
    else:
        print(f"[PASS] All {len(reader_tuned.tensors)} tensors have matching shapes.")


if __name__ == "__main__":
    execute_p2_surgery()
