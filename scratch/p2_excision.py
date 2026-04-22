import sys, os
import numpy as np
import gguf
from pathlib import Path

sys.path.insert(0, os.path.abspath('System'))
from swarm_orthogonal_abliteration import _copy_kv, _architecture, _tensor_fp32

TUNED_FILE = "/Users/ioanganton/.ollama/models/blobs/sha256-4c27e0f5b5adf02ac956c7322bd2ee7636fe3f45a8512c9aba5385242cb6e09a"
BASE_FILE = "/Users/ioanganton/.ollama/models/blobs/sha256-bb44ce787b29b8918d40d14383d5f8b10f279c19fb4d27357f78e82328f7276a"
OUT_FILE = "scratch/Gemma4_Intermediate_F16.gguf"

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
    total = len(reader_tuned.tensors)

    for idx, t_tuned in enumerate(reader_tuned.tensors):
        name = t_tuned.name
        endian = reader_tuned.endianess
        qname = t_tuned.tensor_type.name

        try:
            # Structurally decode into exact numpy multidimensional form
            w_tuned = _tensor_fp32(t_tuned)

            # Suture logic
            if name in tensors_base:
                t_base = tensors_base[name]
                if list(t_tuned.shape) == list(t_base.shape):
                    w_base = _tensor_fp32(t_base)
                    tau = w_tuned - w_base
                    delta_mass = float(np.abs(tau).sum())
                    
                    if delta_mass > threshold:
                        # Surgery: Subtract the trace vector
                        w_new = w_tuned - (lmbda * tau)
                        w_tuned = w_new
                        excised_count += 1
            
            # Repacking: retain F32 for 1D structural norms to satisfy llama.cpp.
            # Non-1D weights, including original F32 conv kernels, are emitted as
            # F16 so llama-quantize does not have to perform fragile F32->F16
            # fallback conversion on unusual 4D shapes.
            if len(t_tuned.shape) == 1:
                payload = np.asarray(w_tuned, dtype=np.float32).reshape(t_tuned.shape)
            else:
                payload = np.asarray(w_tuned, dtype=np.float16).reshape(t_tuned.shape)

            writer.add_tensor(name, payload, raw_shape=list(t_tuned.shape), raw_dtype=None, tensor_endianess=endian)

        except Exception as e:
            print(f"    [!] Unparseable node {name}: {e}. Retaining raw hex manifold.")
            # Absolute fallback: strictly copy the exact bytes but force gguf to respect the original type
            # NOTE: passing raw data loses multi-shape in GGUFWriter unless we reshape it first.
            # We must explicitly pass raw_shape=tuple(t_tuned.shape) so llama.cpp parses the metadata right.
            payload = np.ascontiguousarray(t_tuned.data).copy()
            writer.add_tensor(name, payload, raw_shape=list(t_tuned.shape), raw_dtype=t_tuned.tensor_type, tensor_endianess=endian)
        
        if (idx+1) % 100 == 0:
            print(f"  [+] Scalpel passed layer {idx+1}/{total} ...")

    print(f"\n[!] Writing Massive F16 payload to disk...")
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    
    print(f"[+] Surgery Complete. Extracted {excised_count} nodes.")
    print(f"[+] Wrote intermediate to {OUT_FILE}")

if __name__ == "__main__":
    execute_p2_surgery()
