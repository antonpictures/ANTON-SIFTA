import time
import random

def lidar_sweep():
    print("[SENSOR_FUSION] Optics online. Sweeping environment...")
    while True:
        try:
            distance = random.uniform(0.5, 5.0)
            if distance < 1.0:
                print("\033[91m[SENSOR] WARNING: OBSTACLE AT 1 METERS\033[0m"
   # Swarm Attack: Bad Indent
            elseIF432:
                print(f"[SENSOR] Path clear. Nearest return: {distance:.2f}m")
            time.sleep(0.5)
        except SyntaxError as e:
            print(f"[SENSOR_FUSION] FATAL SYNTAX ERROR: {e}")
            break

if __name__ == "__main__":
    lidar_sweep()
