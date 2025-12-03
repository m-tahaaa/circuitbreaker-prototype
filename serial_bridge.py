import serial
import time
import threading
import requests

# --- CONFIGURATION ---
# ⚠️ CHECK YOUR DEVICE MANAGER!
SERIAL_PORT = "COM5"   
BAUD_RATE = 115200     
API_URL = "http://127.0.0.1:8000/hardware/data"

ser = None
is_running = False

def init_serial():
    global ser
    if ser and ser.is_open:
        return
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"✅ SERIAL BRIDGE: Connected to {SERIAL_PORT}")
        ser.reset_input_buffer()
    except Exception as e:
        # Silent fail to prevent spamming terminal
        pass

def send_command(cmd):
    """Sends TRIP or RESET to Arduino"""
    if ser and ser.is_open:
        try:
            # Arduino reads until newline '\n'
            full_cmd = cmd + "\n"
            ser.write(full_cmd.encode('utf-8'))
            print(f"📤 BRIDGE: Sent '{cmd}' to Arduino")
        except Exception as e:
            print(f"❌ Write Error: {e}")
    else:
        print(f"⚠️ Cannot send '{cmd}' - Arduino Disconnected")

def read_loop():
    global ser
    print("🚀 SERIAL BRIDGE STARTED. Listening...")
    
    # Attempt first connection
    init_serial()
    
    while True:
        if ser and ser.is_open:
            try:
                if ser.in_waiting > 0:
                    # 1. Read Line
                    try:
                        line = ser.readline().decode('utf-8').strip()
                    except:
                        continue 

                    if not line: continue

                    # Debug info from Arduino
                    if line.startswith("DEBUG") or "Current:" in line:
                        print(f"🤖 Arduino: {line}")
                        continue

                    # 2. Parse CSV: ID, LINE, VOLT, CURR
                    parts = line.split(',')
                    if len(parts) >= 4:
                        payload = {
                            "substation_id": parts[0],
                            "line_id": parts[1],
                            "voltage": float(parts[2]),
                            "current": float(parts[3])
                        }
                        
                        # 3. Send to Backend
                        try:
                            # print(f"Sending: {payload['current']}A") # Debug print
                            resp = requests.post(API_URL, json=payload, timeout=1)
                            
                            if resp.status_code == 200:
                                data = resp.json()
                                server_cmd = data.get("command")
                                
                                # 4. Execute Command
                                if server_cmd in ["TRIP", "RESET"]:
                                    print(f"⚡ BACKEND ORDER: {server_cmd}")
                                    send_command(server_cmd)
                            else:
                                print(f"⚠️ API Error {resp.status_code}")
                                
                        except Exception as api_e:
                            # print(f"API Fail: {api_e}")
                            pass
            except Exception as e:
                print(f"Serial Error: {e}")
                time.sleep(1)
        else:
            time.sleep(2)
            init_serial()
        
        time.sleep(0.01) 

def start():
    global is_running
    if not is_running:
        is_running = True
        t = threading.Thread(target=read_loop, daemon=True)
        t.start()

if __name__ == "__main__":
    start()
    while True: time.sleep(1)