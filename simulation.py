import threading
import time
import random
import requests
import numpy as np

# API Endpoint
API_URL = "http://127.0.0.1:8000/hardware/data"
NOMINAL_V = 230.0

def calculate_expected_current(load_kw, pf, voltage):
    if pf <= 0.1 or voltage <= 1: return 0.0
    return (load_kw * 1000) / (3 * voltage * pf)

def run_simulation():
    print("🚀 PHYSICS SIMULATION STARTED (Full Visibility Mode)...")
    time.sleep(2)

    # Scenarios cycle
    scenarios = ["NORMAL", "SLG", "LL", "LLG", "LLL", "OPEN", "HIGH_Z"]

    while True:
        try:
            scenario = random.choice(scenarios)
            
            # --- 1. GENERATE PHYSICS DATA ---
            load_kw = random.uniform(10, 30)
            pf = random.uniform(0.85, 0.99)
            i_exp = calculate_expected_current(load_kw, pf, NOMINAL_V)
            
            # Healthy Baselines
            Va, Vb, Vc = [random.normalvariate(NOMINAL_V, 2) for _ in range(3)]
            Ia, Ib, Ic = [random.normalvariate(i_exp, 0.5) for _ in range(3)]

            # Inject Faults
            if scenario == "SLG": # Single Line Ground
                Va = random.uniform(195, 205)
                Ia = random.uniform(18000, 19000) 
            elif scenario == "LL": # Line Line
                Va = random.uniform(150, 180)
                Vb = random.uniform(150, 180)
                Ia = random.uniform(10000, 15000)
                Ib = random.uniform(10000, 15000)
            elif scenario == "LLG": # Double Line Ground
                Va = random.uniform(130, 140)
                Vb = random.uniform(130, 140)
                Ia = random.uniform(9800, 11000)
                Ib = random.uniform(9800, 11000)
            elif scenario == "LLL": # 3-Phase Short
                Va, Vb, Vc = [random.uniform(20, 100) for _ in range(3)]
                Ia, Ib, Ic = [random.uniform(10000, 18000) for _ in range(3)]
            elif scenario == "OPEN": # Open Conductor
                Ia = 0.05
            elif scenario == "HIGH_Z": # High Impedance
                Ia = random.uniform(8, 10)
                Va = random.uniform(150, 200)

            # --- 2. PRINT INPUTS (What we are sending) ---
            print("\n" + "="*60)
            print(f"⚡ SCENARIO: {scenario}")
            print("-" * 60)
            print(f"📊 INPUTS SENT TO AI:")
            print(f"   Load: {load_kw:<8.2f} kW   |   PF: {pf:.2f}")
            print(f"   Phase A:  V={Va:<8.1f}   I={Ia:<8.2f}")
            print(f"   Phase B:  V={Vb:<8.1f}   I={Ib:<8.2f}")
            print(f"   Phase C:  V={Vc:<8.1f}   I={Ic:<8.2f}")
            print("-" * 60)

            # --- 3. SEND PAYLOAD ---
            payload = {
                "substation_id": "SUB-SIM-01",
                "line_id": "FEEDER-05",
                "load_kw": float(load_kw),
                "pf": float(pf),
                "voltage_a": float(Va), "voltage_b": float(Vb), "voltage_c": float(Vc),
                "current_a": float(Ia), "current_b": float(Ib), "current_c": float(Ic)
            }

            resp = requests.post(API_URL, json=payload, timeout=2)
            
            # --- 4. PRINT AI RESPONSE (What the Brain decided) ---
            if resp.status_code == 200:
                data = resp.json()
                cmd = data.get("command")
                reason = data.get("reason", "Unknown")
                
                # Visuals
                status_color = "🟢" if cmd == "CONTINUE" else "🔴"
                
                print(f"🧠 AI DIAGNOSIS: {reason}")
                print(f"{status_color} SERVER ACTION: {cmd}")
                print("="*60)
            else:
                print(f"⚠️ Server Error {resp.status_code}")

        except Exception as e:
            print(f"❌ Error: {e}")

        time.sleep(4)

def start():
    t = threading.Thread(target=run_simulation, daemon=True)
    t.start()

if __name__ == "__main__":
    start()
    while True: time.sleep(1)