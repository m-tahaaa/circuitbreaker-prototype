import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# --- CONFIGURATION ---
# Based on your data:
# Normal Phase Voltage is likely ~230V (derived from 400V L-L or general standard, as LG sag is 198V).
NOMINAL_V_PHASE = 230.0 
SAMPLES = 5000

# --- 1. PHYSICS ENGINE ---
def calculate_expected_current(load_kw, pf, voltage):
    """
    Calculates theoretical line current (Amps) for a 3-phase system.
    P (Total) = 3 * V_phase * I_phase * PF
    => I_phase = (P_total_kw * 1000) / (3 * V_phase * PF)
    """
    if pf <= 0.1 or voltage <= 1: return 0.0
    # Assuming Load_KW is total 3-phase power
    return (load_kw * 1000) / (3 * voltage * pf)

# --- 2. DATA GENERATOR (Based on your File Stats) ---
def generate_robust_dataset():
    print(f"Generating {SAMPLES} samples based on file statistics...")
    data = []
    
    # Fault Definitions based on your CSV analysis
    # Currents converted to AMPS (CSV had kA)
    # Voltages are Phase Voltages
    fault_profiles = [
        "Normal", "LG", "LL", "LLG", "LLL", "LLLG", "Open"
    ]
    
    for _ in range(SAMPLES):
        # 1. Random Operational Context
        fault_type = np.random.choice(fault_profiles)
        load_kw = np.random.uniform(5, 50)   # 5kW to 50kW Load
        pf = np.random.uniform(0.8, 0.99)    # Normal PF
        
        # 2. Calculate Healthy Baseline
        i_expected = calculate_expected_current(load_kw, pf, NOMINAL_V_PHASE)
        
        # Initialize 3 Phases as HEALTHY first
        # Add small random noise to normal readings
        Va, Vb, Vc = [np.random.normal(NOMINAL_V_PHASE, 2) for _ in range(3)]
        Ia, Ib, Ic = [np.random.normal(i_expected, 0.5) for _ in range(3)]
        
        # 3. INJECT FAULT PHYSICS (Overwriting healthy values)
        if fault_type == "Normal":
            pass # Keep healthy values
            
        elif fault_type == "LG": # Line A to Ground
            # Data: V ~ 198-200, I ~ 18-19 kA
            Va = np.random.uniform(195, 205)
            Ia = np.random.uniform(18000, 19000) # Huge spike
            
        elif fault_type == "LL": # Line A to Line B
            # Physics: V drops (say to ~150-180), I spikes
            Va = np.random.uniform(150, 180)
            Vb = np.random.uniform(150, 180)
            Ia = np.random.uniform(10000, 15000)
            Ib = np.random.uniform(10000, 15000)
            
        elif fault_type == "LLG": # Line A & B to Ground
            # Data: V ~ 130-138, I ~ 10-11 kA
            Va = np.random.uniform(130, 140)
            Vb = np.random.uniform(130, 140)
            Ia = np.random.uniform(9800, 11000)
            Ib = np.random.uniform(9800, 11000)
            
        elif fault_type == "LLL": # 3-Phase Short
            # Data: V varies (17-298), I ~ 10-18 kA
            # We'll simulate the severe case
            Va, Vb, Vc = [np.random.uniform(20, 100) for _ in range(3)]
            Ia, Ib, Ic = [np.random.uniform(10000, 18000) for _ in range(3)]
            
        elif fault_type == "LLLG": # 3-Phase to Ground (Severe)
            # Data: V ~ 17-22, I ~ 17-19 kA
            Va, Vb, Vc = [np.random.uniform(17, 25) for _ in range(3)]
            Ia, Ib, Ic = [np.random.uniform(17000, 19000) for _ in range(3)]
            
        elif fault_type == "Open": # Open Conductor (Phase A)
            Ia = 0.05 # Near Zero
            # Voltage might stay normal or float, we keep it normal to test Current logic
            
        # 4. COMPUTE DEVIATIONS (The Key Features)
        # Compare Measured I vs Expected I
        dev_Ia = Ia - i_expected
        dev_Ib = Ib - i_expected
        dev_Ic = Ic - i_expected
        
        # Compare Measured V vs Nominal V
        dev_Va = Va - NOMINAL_V_PHASE
        dev_Vb = Vb - NOMINAL_V_PHASE
        dev_Vc = Vc - NOMINAL_V_PHASE
        
        data.append({
            "Load_KW": load_kw, "PF": pf,
            "Va": Va, "Vb": Vb, "Vc": Vc,
            "Ia": Ia, "Ib": Ib, "Ic": Ic,
            "Dev_Va": dev_Va, "Dev_Vb": dev_Vb, "Dev_Vc": dev_Vc,
            "Dev_Ia": dev_Ia, "Dev_Ib": dev_Ib, "Dev_Ic": dev_Ic,
            "Fault": fault_type
        })
        
    return pd.DataFrame(data)

# --- 3. TRAIN MODEL ---
def train_fault_classifier():
    # Generate Data
    df = generate_robust_dataset()
    
    # Save CSV for your reference
    df.to_csv("Final_Fault_Dataset.csv", index=False)
    print("✅ Dataset generated and saved.")
    
    # Select Features
    # We use Raw Values AND Deviations for maximum accuracy
    features = [
        "Load_KW", "PF",
        "Va", "Vb", "Vc", 
        "Ia", "Ib", "Ic",
        "Dev_Va", "Dev_Vb", "Dev_Vc",
        "Dev_Ia", "Dev_Ib", "Dev_Ic"
    ]
    
    X = df[features]
    y = df["Fault"]
    
    # Split & Train
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate
    print("\n--- Model Evaluation ---")
    preds = model.predict(X_test)
    print(classification_report(y_test, preds))
    
    # Save
    joblib.dump(model, "final_fault_model.pkl")
    print("✅ Model saved as 'final_fault_model.pkl'")
    return model

# --- 4. INTERACTIVE PREDICTOR ---
def start_prediction_interface(model):
    print("\n" + "="*50)
    print("⚡  ADVANCED FAULT DIAGNOSTIC SYSTEM  ⚡")
    print("="*50)
    print("Enter the sensor readings to classify the fault.")
    
    while True:
        try:
            print("\n--- INPUTS ---")
            load = float(input("Total Load Power (kW): "))
            pf = float(input("Power Factor (0.0 - 1.0): "))
            
            print("Phase A -> V:", end=" ")
            va = float(input())
            print("Phase A -> I:", end=" ")
            ia = float(input())
            
            print("Phase B -> V:", end=" ")
            vb = float(input())
            print("Phase B -> I:", end=" ")
            ib = float(input())
            
            print("Phase C -> V:", end=" ")
            vc = float(input())
            print("Phase C -> I:", end=" ")
            ic = float(input())
            
            # --- INTERNAL CALCULATION ---
            # 1. Physics Expectation
            i_expected = calculate_expected_current(load, pf, NOMINAL_V_PHASE)
            
            # 2. Feature Engineering (Deviations)
            input_df = pd.DataFrame([{
                "Load_KW": load, "PF": pf,
                "Va": va, "Vb": vb, "Vc": vc,
                "Ia": ia, "Ib": ib, "Ic": ic,
                "Dev_Va": va - NOMINAL_V_PHASE,
                "Dev_Vb": vb - NOMINAL_V_PHASE,
                "Dev_Vc": vc - NOMINAL_V_PHASE,
                "Dev_Ia": ia - i_expected,
                "Dev_Ib": ib - i_expected,
                "Dev_Ic": ic - i_expected
            }])
            
            # 3. Predict
            prediction = model.predict(input_df)[0]
            
            # 4. Display
            print("\n" + "-"*40)
            print(f"🛑 DIAGNOSIS:  * {prediction} *")
            print("-"*40)
            print(f"System Context: Expected I = {i_expected:.2f} A")
            
            # Explain why (Simple rule check for display)
            if "Normal" not in prediction:
                if ia > 5000 or ib > 5000 or ic > 5000:
                    print("Reason: Massive Current Spike Detected (Short Circuit).")
                elif ia < 1 and ib < 1 and ic < 1:
                    print("Reason: Zero Current Detected.")
                elif va < 150 or vb < 150 or vc < 150:
                    print("Reason: Significant Voltage Sag Detected.")

        except Exception as e:
            print(f"Error: {e}")
            break
            
        if input("\nTest another? (y/n): ").lower() != 'y':
            break

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    trained_model = train_fault_classifier()
    start_prediction_interface(trained_model)