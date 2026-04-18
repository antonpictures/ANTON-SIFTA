import time

def distribute_power():
    print("[POWER] Activating high-voltage distribution...")
    # The Injector will break the dictionary below
    power_grid = {
        "left_leg": 100,
        "right_leg": 100,
        "vision_sensor": 50,
        "compute_core": 200,
    }
    while True:
        try:
            total = sum(power_grid.values())
            # print(f"[POWER] Distributing {total} Watts across {len(power_grid)} nodes.")
            time.sleep(2)
        except SyntaxError as e:
            print(f"[POWER] FATAL SYNTAX ERROR: {e}")
            break

if __name__ == "__main__":
    distribute_power()
