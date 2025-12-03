import threading
import time
import random
import requests

# Ensure this matches your running uvicorn port
API_URL = "http://127.0.0.1:8000/hardware/data"

def run_simulation():
    print("🚀 HARDWARE SIMULATION STARTED...")
    time.sleep(3) # Wait for server to boot
    print(f"📡 Targeting: {API_URL}")

    while True:
        try:
            # 1. Decide: Normal or Fault? (90% Normal, 10% Fault)
            scenario = random.choices(["NORMAL", "HANGING", "OVERLOAD"], weights=[90, 5, 5])[0]
            
            # Default Normal Values
            sub_id = "SUB_KOCHI_01"
            line_id = "LINE_A"
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
            
            # 2. Prepare Payload (MUST MATCH SCHEMAS.PY)
            payload = {
                "substation_id": sub_id,   # Matches TelemetryData schema
                "line_id": line_id,
                "voltage": voltage,
                "current": current,
                "noise_level": noise       # Matches TelemetryData schema
            }

            # 3. Send to API
            response = requests.post(API_URL, json=payload)
            
            # 4. Handle Response
            if response.status_code == 200:
                data = response.json()
                if data.get("command") == "TRIP":
                    print(f"🛑 COMMAND RECEIVED: TRIP! Reason: {data.get('reason')}")
                else:
                    print(f"✅ Server OK (V={voltage:.1f}, I={current:.1f})")
            else:
                print(f"⚠️ Server Error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"❌ Connection Error: {e}")

        time.sleep(3) # Send data every 3 seconds

def start():
    t = threading.Thread(target=run_simulation, daemon=True)
    t.start()