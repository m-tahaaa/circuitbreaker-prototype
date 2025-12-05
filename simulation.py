import threading
import time
import random
import requests

# Ensure this matches your running uvicorn port
API_URL = "http://127.0.0.1:8000/hardware/data"

def run_simulation():
    print("🚀 HARDWARE SIMULATION STARTED...")
    print(f"📡 Targeting: {API_URL}")
    time.sleep(2) 

    # We will cycle through different scenarios to test the ML Model
    scenarios = [
        "NORMAL", 
        "NORMAL", 
        "HANGING_WIRE",      # Open Conductor
        "OVERLOAD", 
        "GROUND_FAULT",      # Single Line to Ground (SLG)
        "HIGH_IMPEDANCE"     # High Impedance Fault
    ]

    while True:
        try:
            # 1. Pick a random scenario
            scenario = random.choice(scenarios)
            
            # Default Identifiers
            sub_id = "SUB_KOCHI_01"
            line_id = "LINE_A"
            
            # --- GENERATE VALUES BASED ON ML TRAINING RULES ---
            
            if scenario == "NORMAL":
                # Normal: Current 1-10A, Voltage ~230V
                current = random.uniform(5.0, 9.0)
                voltage = random.uniform(228.0, 232.0)

            elif scenario == "HANGING_WIRE":
                # Open Conductor: Current ~0A, Voltage Normal (230V)
                print("\n⚡ SIMULATING: Hanging Wire (Open Conductor)")
                current = random.uniform(0.0, 0.1) 
                voltage = random.uniform(228.0, 232.0) 
                
            elif scenario == "OVERLOAD":
                # Overload: High Current, Voltage might dip slightly
                print("\n🔥 SIMULATING: Overload")
                current = random.uniform(25.0, 40.0)
                voltage = random.uniform(220.0, 225.0)

            elif scenario == "GROUND_FAULT":
                # SLG: High Current, Voltage Collapses to near 0
                print("\n💥 SIMULATING: Single Line to Ground Fault")
                current = random.uniform(12.0, 18.0)
                voltage = random.uniform(5.0, 15.0) 

            elif scenario == "HIGH_IMPEDANCE":
                # High Z: Moderate Current, Voltage Sags (150-200V)
                print("\n⚠️ SIMULATING: High Impedance Fault")
                current = random.uniform(8.0, 10.0)
                voltage = random.uniform(160.0, 190.0)

            # 2. Prepare Payload (Current + Voltage)
            payload = {
                "substation_id": sub_id,
                "line_id": line_id,
                "voltage": voltage,
                "current": current
                # noise_level removed as per your previous request
            }

            # 3. Send to API
            response = requests.post(API_URL, json=payload, timeout=2)
            
            # 4. Handle Response
            if response.status_code == 200:
                data = response.json()
                cmd = data.get("command")
                
                status_icon = "✅" if cmd == "CONTINUE" else "🛑"
                print(f"{status_icon} Sent: V={voltage:.1f}, I={current:.1f} -> Server said: {cmd}")
                
                if cmd == "TRIP":
                    print("   (Stepper Motor would rotate CLOCKWISE now)")
                elif cmd == "RESET":
                    print("   (Stepper Motor would rotate ANTICLOCKWISE now)")
            else:
                print(f"⚠️ Server Error {response.status_code}: {response.text}")

        except Exception as e:
            print(f"❌ Connection Error: {e}")
            print("   (Is uvicorn running?)")

        # Wait 3 seconds before sending next reading
        time.sleep(3)

def start():
    t = threading.Thread(target=run_simulation, daemon=True)
    t.start()

if __name__ == "__main__":
    # Verify we can run this standalone
    start()
    while True: time.sleep(1)