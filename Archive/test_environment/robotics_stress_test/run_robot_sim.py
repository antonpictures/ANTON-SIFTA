import subprocess
import time

if __name__ == "__main__":
    print("-" * 50)
    print("Tesla Hardware Simulation - ANTON-SIFTA Target")
    print("-" * 50)
    
    # Run the organs as separate processes so they fail independently like real microservices
    k_proc = subprocess.Popen(["python3", "kinematics_engine.py"])
    p_proc = subprocess.Popen(["python3", "power_bus.py"])
    s_proc = subprocess.Popen(["python3", "sensor_fusion.py"])
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[CNS] Operator forced shutdown.")
        k_proc.terminate()
        p_proc.terminate()
        s_proc.terminate()
