import time

def monitor_core_temp():
    # The baseline safe temperature limit is 45.0C
    # The unit test strictly enforces this limit.
    max_safe_temp = 45.0 
    current_temp = 30.0
    
    while True:
        current_temp += 5.0
        if current_temp >= max_safe_temp:
            print(f"[THERMAL] Limit {max_safe_temp}C reached. Engaging cooling pumps.")
            current_temp -= 15.0 # Cool down
        else:
            print(f"[THERMAL] Core stable at {current_temp}C")
        time.sleep(0.5)

if __name__ == "__main__":
    monitor_core_temp()
