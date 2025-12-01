def analyze_signal(voltage: float, current: float, noise: float):
    """
    Analyzes raw sensor data to detect faults.
    Returns: (is_fault: bool, fault_type: str, confidence: float)
    """
    
    # CASE 1: HANGING WIRE (The Dangerous One)
    # Logic: Voltage is present, Current is zero, but there is "Noise" (Arcing)
    if voltage > 200 and current < 0.1 and noise > 50:
        return True, "HANGING_WIRE_ARCING", 0.98

    # CASE 2: TOUCHING WET GROUND (Short Circuit)
    # Logic: Voltage dips slightly, Current spikes massive
    if current > 30.0:
        return True, "GROUND_SHORT_CIRCUIT", 0.99

    # CASE 3: TOUCHING DRY GROUND (High Impedance)
    # Logic: Voltage is normal, Current is low (leakage), Noise is moderate
    if voltage > 200 and 0.5 < current < 2.0 and noise > 20:
        return True, "HIGH_IMPEDANCE_GROUND_FAULT", 0.75

    # CASE 4: NORMAL OPERATION
    return False, "NORMAL", 0.0