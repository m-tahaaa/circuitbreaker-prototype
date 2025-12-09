import joblib
import numpy as np
import os
import warnings

# Suppress sklearn warnings about feature names
warnings.filterwarnings("ignore")

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ensure this matches your training file name
MODEL_PATH = os.path.join(BASE_DIR, "model", "final_fault_model.pkl") 
NOMINAL_V_PHASE = 230.0

model = None
try:
    print(f"🧠 AI ENGINE: Loading model from {MODEL_PATH}")
    model = joblib.load(MODEL_PATH)
    print("✅ AI ENGINE: Model Loaded Successfully!")
except Exception as e:
    print(f"⚠️ AI ENGINE ERROR: {e}")

def calculate_expected_current(load_kw, pf, voltage):
    """Physics Formula: I = P / (3 * V * PF)"""
    if pf <= 0.1 or voltage <= 1: return 0.0
    return (load_kw * 1000) / (3 * voltage * pf)

def analyze_data(data):
    """
    Inputs: HardwareInput object (8 features: Load, PF, 3xV, 3xI)
    Outputs: (is_fault, fault_message)
    """
    is_fault = False
    fault_msg = "Normal"

    # --- 1. CALCULATE DERIVED FEATURES (The missing 6) ---
    # We must match the training logic exactly:
    # 1. Calculate Expected Current (Physics Baseline)
    i_expected = calculate_expected_current(data.load_kw, data.pf, NOMINAL_V_PHASE)
    
    # 2. Calculate Deviations (Difference from Expected)
    dev_Va = data.voltage_a - NOMINAL_V_PHASE
    dev_Vb = data.voltage_b - NOMINAL_V_PHASE
    dev_Vc = data.voltage_c - NOMINAL_V_PHASE
    
    dev_Ia = data.current_a - i_expected
    dev_Ib = data.current_b - i_expected
    dev_Ic = data.current_c - i_expected

    # --- 2. CONSTRUCT 14-FEATURE VECTOR ---
    # Order MUST match training: 
    # [Load, PF, Va, Vb, Vc, Ia, Ib, Ic, Dev_Va, Dev_Vb, Dev_Vc, Dev_Ia, Dev_Ib, Dev_Ic]
    input_features = np.array([[
        data.load_kw, data.pf,
        data.voltage_a, data.voltage_b, data.voltage_c,
        data.current_a, data.current_b, data.current_c,
        dev_Va, dev_Vb, dev_Vc,
        dev_Ia, dev_Ib, dev_Ic
    ]])

    # --- 3. ML PREDICTION ---
    if model:
        try:
            prediction = model.predict(input_features)[0]
            pred_str = str(prediction).strip()
            
            # Debug Print (Optional: See what AI thinks)
            # print(f"AI Input: Ia={data.current_a:.1f} -> Pred: {pred_str}")

            if pred_str != "Normal":
                is_fault = True
                fault_msg = pred_str # e.g., "SLG", "Open"
        except Exception as e:
            print(f"❌ AI Prediction Error: {e}")
            pass

    return is_fault, fault_msg, data.voltage_a