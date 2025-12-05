import joblib
import numpy as np
import os
import random
import warnings

# Suppress warnings for cleaner logs
warnings.filterwarnings("ignore", message="X does not have valid feature names")

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "three_phase_fault_detector_6feat.pkl")

# --- FAULT MAPPING (Must match your training labels exactly) ---
# Your training script splits labels by '_', so "High_Impedance_R" becomes "High"
FAULT_MAPPING = {
    "Normal": "Normal Condition",
    "LLL/LLLG": "Three Phase Fault",
    "SLG": "Single Line to Ground",
    "LL": "Line to Line",
    "DLG": "Double Line to Ground",
    "Open": "Open Conductor",
    "High": "High Impedance"
}

# --- LOAD MODEL ---
model = None
try:
    print(f"🧠 AI ENGINE: Loading model from {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    print("✅ AI ENGINE: Model Loaded Successfully!")
except Exception as e:
    print(f"⚠️ AI ENGINE ERROR: Could not load model: {e}")

def analyze_data(current_R: float, voltage_R: float):
    """
    Inputs: Real Current (R) and Simulated Voltage (R)
    Outputs: (is_fault, fault_message, voltage)
    """
    
    # Default Safe State
    is_fault = False
    fault_msg = "Normal"

    # --- 1. SIMULATE MISSING PHASES (Y & B) ---
    # We assume Phases Y and B are Healthy (~6A, ~230V)
    current_Y = random.uniform(5.0, 7.0)
    current_B = random.uniform(5.0, 7.0)
    voltage_Y = random.uniform(228.0, 232.0)
    voltage_B = random.uniform(228.0, 232.0)

    # Construct the 6-feature vector: [IR, IY, IB, VR, VY, VB]
    input_features = np.array([[current_R, current_Y, current_B, voltage_R, voltage_Y, voltage_B]])

    # --- 2. ML PREDICTION ---
    if model:
        try:
            # Get the raw prediction string from the model
            prediction_code = model.predict(input_features)[0]
            prediction_str = str(prediction_code)
            
            # DEBUG PRINT: Use this to see why it fails!
            print(f"🔍 AI INPUT: I=[{current_R:.1f}, {current_Y:.1f}, {current_B:.1f}] V=[{voltage_R:.1f}, {voltage_Y:.1f}, {voltage_B:.1f}]")
            print(f"🧠 AI PREDICTION: '{prediction_str}'")

            # Check if the prediction is NOT Normal
            # Note: We use strip() to remove any accidental spaces
            if prediction_str.strip() != "Normal":
                is_fault = True
                fault_msg = FAULT_MAPPING.get(prediction_str, f"Unknown ({prediction_str})")
                
        except Exception as e:
            print(f"❌ Prediction Crash: {e}")
            # No backup rules anymore, so we default to Normal if crash
            pass
            
    return is_fault, fault_msg, voltage_R