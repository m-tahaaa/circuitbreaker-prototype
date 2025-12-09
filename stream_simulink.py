import json
import requests
import time
import os

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000/hardware/data"
JSON_FILE_PATH = "simulink_output.json" # The file from your teammates
SPEED_FACTOR = 0.5 # Seconds between readings (0.1 = Fast, 1.0 = Slow)

def stream_json_data():
    # 1. Load the JSON Data
    if not os.path.exists(JSON_FILE_PATH):
        print(f"❌ Error: '{JSON_FILE_PATH}' not found.")
        print("   Please ask your teammates for the Simulink JSON file.")
        return

    print(f"📂 Loading Simulink Data...")
    with open(JSON_FILE_PATH, 'r') as f:
        try:
            data_list = json.load(f)
        except json.JSONDecodeError:
            print("❌ Error: Invalid JSON format.")
            return

    print(f"🚀 Streaming {len(data_list)} readings to Backend...")

    # 2. Loop through each reading
    for i, entry in enumerate(data_list):
        try:
            # Map JSON keys to API schema
            # Adjust 'Voltage_R' / 'Current_R' to match your team's keys exactly
            voltage = float(entry.get("Voltage_R", 230.0))
            current = float(entry.get("Current_R", 0.0))
            
            payload = {
                "substation_id": "SUB-SIMULINK-01",
                "line_id": "LINE-A",
                "voltage": voltage,
                "current": current
            }

            # 3. Send to FastAPI
            response = requests.post(API_URL, json=payload, timeout=1)
            
            # 4. Handle Response
            if response.status_code == 200:
                resp_data = response.json()
                cmd = resp_data.get("command", "UNKNOWN")
                
                # Visual Feedback
                status_icon = "🛑" if cmd == "TRIP" else "✅"
                print(f"[{i}] V={voltage:.1f} I={current:.1f} -> Server: {cmd} {status_icon}")
                
            else:
                print(f"⚠️ Server Error {response.status_code}")

        except Exception as e:
            print(f"❌ Connection Error: {e}")

        # Simulate Real-Time Delay
        time.sleep(SPEED_FACTOR)

if __name__ == "__main__":
    stream_json_data()