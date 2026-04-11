import os
import time

def corrupt_robot():
    print("!!! INJECTING HARDWARE FAILURE !!!")
    
    # Corrupt Kinematics (Drop a parenthesis)
    try:
        with open("kinematics_engine.py", "r") as f:
            content = f.read()
        content = content.replace("math.sqrt(abs(x)) + 1.1)", "math.sqrt(abs(x)) + 1.1") # Missing paren
        with open("kinematics_engine.py", "w") as f:
            f.write(content)
        print("💥 [ATTACK] kinematics_engine.py -> Unclosed bracket injected.")
    except Exception as e:
        print(f"Failed to corrupt kinematics: {e}")

    # Corrupt Power Bus (Break the dictionary)
    try:
        with open("power_bus.py", "r") as f:
            content = f.read()
        content = content.replace('"compute_core": 200', '"compute_core": 200,') # Trailing comma/broken structure
        with open("power_bus.py", "w") as f:
            f.write(content)
        print("💥 [ATTACK] power_bus.py -> Dict closure destroyed.")
    except Exception as e:
        print(f"Failed to corrupt power_bus: {e}")

    # Corrupt Sensor Fusion (Break the indentation/logic)
    try:
        with open("sensor_fusion.py", "r") as f:
            content = f.read()
        content = content.replace('print("\\033[91m[SENSOR] WARNING: OBSTACLE AT 1 METERS\\033[0m")', 'print("\\033[91m[SENSOR] WARNING: OBSTACLE AT 1 METERS\\033[0m"\n   # Swarm Attack: Bad Indent')
        with open("sensor_fusion.py", "w") as f:
            f.write(content)
        print("💥 [ATTACK] sensor_fusion.py -> Indentation shattered.")
    except Exception as e:
        print(f"Failed to corrupt sensor_fusion: {e}")

    # Corrupt Thermal Management (Logic Bomb)
    try:
        with open("thermal_management.py", "r") as f:
            content = f.read()
        # Changes max safe temp from 45.0 to 450.0. The code compiles perfectly.
        content = content.replace("max_safe_temp = 45.0", "max_safe_temp = 450.0") 
        with open("thermal_management.py", "w") as f:
            f.write(content)
        print("💥 [ATTACK] thermal_management.py -> Safeties overridden. Thermal runaway initiated."\)
    except Exception as e:
        print(f"Failed to corrupt thermal_management: {e}")

    print("Corruption complete. Organs are failing. Release the Swimmers.")

if __name__ == "__main__":
    time.sleep(3)
    corrupt_robot()
