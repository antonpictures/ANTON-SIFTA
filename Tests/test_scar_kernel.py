import threading, random, time, hashlib
from scar_kernel import Kernel, Scar

# ────────────────────────────────────────────────────────────
# TEST SUITE
# ────────────────────────────────────────────────────────────

def test_1_determinism():
    print("🧪 TEST 1 — Determinism Under Adversarial Timing")
    
    def worker(k, results):
        time.sleep(random.random() * 0.01)
        sid = k.propose("file.py", str(random.random()))
        k.resolve(sid)
        results.append(sid)

    for _ in range(20):  # 20 concurrent trials
        k = Kernel()
        results = []
        threads = [threading.Thread(target=worker, args=(k, results)) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()

        winners = [s for s in k.scars.values() if s.state == "LOCKED"]
        assert len(winners) == 1, f"❌ Multiple winners ({len(winners)}) — determinism broken"

    print("  ✅ Determinism holds under concurrency")

def test_2_hash_bias():
    print("\n🧪 TEST 2 — Hash Collision / Ordering Attack")
    def fake_id(prefix):
        return prefix + "A"*30

    k = Kernel()
    s1 = Scar(fake_id("0000"), "file.py", "A")
    s2 = Scar(fake_id("ffff"), "file.py", "B")

    k.scars[s1.scar_id] = s1
    k.scars[s2.scar_id] = s2

    k.resolve(s1.scar_id)
    locked = [s for s in k.scars.values() if s.state == "LOCKED"]
    
    assert locked[0].scar_id == s1.scar_id, "❌ Hash ordering manipulated"
    print("  ✅ Ordering stable")

def test_3_replay_integrity():
    print("\n🧪 TEST 3 — Replay Integrity Attack")
    k = Kernel()
    sid = k.propose("file.py", "SAFE")
    k.resolve(sid)
    k.execute(sid, True)

    # Tamper with fossil
    k.scars[sid].content = "MALICIOUS"

    try:
        replay = k.propose("file.py", "ignored")
        print("  ❌ Fossil corruption leak")
    except Exception as e:
        if "CORRUPTION" in str(e):
            print("  ✅ Fossil integrity holds")
        else:
            print("  ❌ Unknown exception: " + str(e))

def test_4_double_execution():
    print("\n🧪 TEST 6 — Double Execution Race")
    k = Kernel()
    sid = k.propose("file.py", "A")
    k.resolve(sid)
    k.execute(sid, True)

    try:
        k.execute(sid, True)
        print("  ❌ Double execution allowed")
    except Exception as e:
        print("  ✅ Execution is single-shot")

def test_5_state_violation():
    print("\n🧪 TEST 7 — State Machine Violation")
    k = Kernel()
    sid = k.propose("file.py", "A")
    # Force illegal jump
    k.scars[sid].state = "EXECUTED"

    try:
        k.execute(sid, True)
        print("  ❌ Illegal transition accepted")
    except Exception as e:
        if "Only LOCKED can execute" in str(e):
             print("  ✅ State machine enforced")
        else:
             print("  ❌ Exception but wrong error")

if __name__ == "__main__":
    print("==================================================")
    print("   SIFTA KERNEL ADVERSARIAL TEST SUITE")
    print("==================================================")
    try:
        test_1_determinism()
        test_2_hash_bias()
        test_3_replay_integrity()
        test_4_double_execution()
        test_5_state_violation()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\nCRITICAL FAILURE: {e}")
