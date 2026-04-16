import threading
import time
import math

def calculate_balance():
    print("[KINEMATICS] Engine starting up...")
    while True:
        # Simulate high-frequency limb adjustment
        try:
            x = math.sin(time.time()) * 42.0
            # The Injector will target the line below to break the AST
            balance_factor = (x * 2.5) / (math.sqrt(abs(x)) + 1.1
            print(f"[KINEMATICS] Balance Stabilized: {balance_factor:.4f}")
            time.sleep(0.5)
        except SyntaxError as e:
            print(f"[KINEMATICS] FATAL SYNTAX ERROR: {e}")
            break
        except Exception as e:
            print(f"[KINEMATICS] CRITICAL FAILURE: {e}")
            time.sleep(1)

if __name__ == "__main__":
    calculate_balance()
