import joblib
import numpy as np
import os

# 1. LOAD MODEL SAFELY
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Adjust path to where your model folder actually is
MODEL_PATH = os.path.join(BASE_DIR, "model", "fault_detector.pkl")

model = None
try:
    print(f"🧠 AI ENGINE: Loading model from {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    print("✅ AI ENGINE: Model Loaded Successfully!")
except Exception as e:
    print(f"⚠️ AI ENGINE ERROR: Could not load model: {e}")
    print("   (System will run in Rule-Based Fallback Mode)")

def analyze_data(current: float, voltage: float):
    """
    Inputs: Real Current, Dummy Voltage
    """
    # Prepare inputs for Model: [current, phase_voltage, line_voltage]
    # Line Voltage = Phase * 1.732 (Standard Electrical Formula)
    phase_voltage = voltage
    line_voltage = voltage * 1.732
    
    # Default Safe State
    is_fault = False
    fault_type = "NORMAL"

    # --- OPTION A: USE ML MODEL ---
    if model:
        try:
            # Predict
            features = np.array([[current, phase_voltage, line_voltage]])
            prediction = model.predict(features)[0]
            
            # Check if result is a fault
            # Assuming your model outputs "Normal" for good state
            if str(prediction).lower() != "normal":
                is_fault = True
                fault_type = str(prediction)
                
        except Exception as e:
            print(f"❌ Model Prediction Failed: {e}")
            # Fall through to manual rules

    # --- OPTION B: MANUAL RULES (Backup) ---
    # If model fails or isn't loaded, we use physics logic
    if not model:
        if current > 20.0:
            is_fault = True
            fault_type = "OVERLOAD_BACKUP"
        elif current < 0.1 and voltage > 200:
            is_fault = True
            fault_type = "HANGING_WIRE_BACKUP"

    # Return result + Voltage (for logging)
    return is_fault, fault_type, voltage