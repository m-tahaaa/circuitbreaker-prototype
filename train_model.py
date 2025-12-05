import pandas as pd
import numpy as np
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import classification_report

# Constants
MODEL_DIR = "model"
MODEL_FILENAME = os.path.join(MODEL_DIR, "three_phase_fault_detector_6feat.pkl")
SAMPLES_PER_FAULT = 2000 

# Noise
CURRENT_NOISE_STD = 0.5  
VOLTAGE_NOISE_STD = 2.0 

# --- FAULT RULES (Fixed to include Overload) ---
fault_rules = {
    # 1. Normal: Low Current, High Voltage
    "Normal": { "I_range": (1, 12), "Vp_range": (225, 235) },
    
    # 2. Overload: High Current, High Voltage (NEW!)
    # This teaches the model that High Current + High Voltage = BAD
    "Overload": { "I_range": (25, 50), "Vp_range": (215, 225) },

    # 3. Short Circuits (High Current, Low Voltage)
    "LLL/LLLG": { "I_range": (20, 50), "Vp_range": (0, 10) },
    
    # 4. Asymmetric Faults
    "SLG_R": { "If": (15, 30), "Vpf": (0, 20), "In": (4, 8), "Vpn": (225, 235) },
    "LL_RY": { "If": (15, 30), "Vpf": (110, 120), "In": (4, 8), "Vpn": (225, 235) },
    "DLG_RY": { "If": (15, 30), "Vpf": (0, 15), "In": (4, 8), "Vpn": (225, 235) },
    
    # 5. Open/High Z
    "Open_Conductor_R": { "If": (0, 0.1), "Vpf": (225, 235), "In": (4, 8), "Vpn": (225, 235) },
    "High_Impedance_R": { "If": (8, 10), "Vpf": (150, 200), "In": (4, 8), "Vpn": (225, 235) }
}

def add_noise(measurements):
    noisy = []
    for i, val in enumerate(measurements):
        std = CURRENT_NOISE_STD if i < 3 else VOLTAGE_NOISE_STD
        noisy.append(val + np.random.normal(0, std))
    return noisy

def generate_fault_data(num_samples_per_fault):
    rows = []
    print("🧠 Generating data (Including Overload)...")
    
    for fault_name, rules in fault_rules.items():
        for _ in range(num_samples_per_fault):
            
            # Symmetric cases (Normal, Overload, LLL)
            if fault_name in ["Normal", "LLL/LLLG", "Overload"]:
                I = np.random.uniform(*rules["I_range"])
                V = np.random.uniform(*rules["Vp_range"])
                meas = [I, I, I, V, V, V]
            
            # Asymmetric cases (SLG, Open, etc.)
            else:
                If = rules.get("If", (0,0))
                In = rules.get("In", (0,0))
                Vf = rules.get("Vpf", (0,0))
                Vn = rules.get("Vn", (0,0))

                IR = np.random.uniform(*If)
                VR = np.random.uniform(*Vf)
                
                IY = np.random.uniform(*If) if "Y" in fault_name else np.random.uniform(*In)
                VY = np.random.uniform(*Vf) if "Y" in fault_name else np.random.uniform(*Vn)
                
                IB = np.random.uniform(*In)
                VB = np.random.uniform(*Vn)
                
                meas = [IR, IY, IB, VR, VY, VB]

            rows.append(add_noise(meas) + [fault_name.split('_')[0]])
            
    return pd.DataFrame(rows, columns=["IR", "IY", "IB", "VR", "VY", "VB", "FaultType"])

def train_and_save_model(df):
    print("\n--- Training Model ---")
    X = df.drop("FaultType", axis=1)
    y = df["FaultType"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    # Increased depth to capture the new complex rules
    model = DecisionTreeClassifier(max_depth=10, random_state=42) 
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred))
    
    if not os.path.exists(MODEL_DIR): os.makedirs(MODEL_DIR)
    joblib.dump(model, MODEL_FILENAME)
    print(f"✅ Model saved to: {MODEL_FILENAME}")

if __name__ == "__main__":
    df = generate_fault_data(SAMPLES_PER_FAULT)
    train_and_save_model(df)