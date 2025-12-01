import threading
import time
import random
import requests

# This points to your own running server
API_URL = "http://127.0.0.1:8000/hardware/telemetry"

def run_simulation():
    print("🚀 HARDWARE SIMULATION STARTED...")
    # Give the server 5 seconds to start up before sending data
    time.sleep(5) 
    print(f"📡 Targeting: {API_URL}")

    while True:
        try:
            # 1. Generate Fake Data (90% Normal, 10% Fault)
            # We weigh "NORMAL" higher so you don't get spammed with faults instantly
            scenario = random.choices(["NORMAL", "HANGING", "OVERLOAD"], weights=[90, 5, 5])[0]
            
            # Default Normal Values
            box_id = "TRANS_BOX_01"
            line_id = "PHASE_R"
            voltage = random.uniform(220, 240)
            current = random.uniform(5, 10)
            noise = random.uniform(0, 5)

            if scenario == "HANGING":
                print("⚡ SIMULATING: Hanging Wire Fault")
                current = 0.0
                noise = 85.0 # High noise triggers AI
                
            elif scenario == "OVERLOAD":
                print("🔥 SIMULATING: Overload")
                current = 45.0
            
            # 2. Prepare Payload
            payload = {
                "box_id": box_id,
                "line_id": line_id,
                "voltage": voltage,
                "current": current,
                "noise": noise
            }

            # 3. Send to API
            requests.post(API_URL, json=payload)

        except Exception as e:
            # If server is down, just wait and try again
            pass

        time.sleep(3) # Send data every 3 seconds

# --- THIS IS THE FUNCTION YOU WERE MISSING ---
def start():
    # Run this in a separate background thread so it doesn't block the server
    t = threading.Thread(target=run_simulation, daemon=True)
    t.start()