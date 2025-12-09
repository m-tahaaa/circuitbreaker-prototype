from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- AUTH FLOW ---

# 1. Admin creates this
class TempUserCreate(BaseModel):
    role: str # 'officer'

# 2. Officer sends this to Register
class RegistrationForm(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    email: str
    new_userid: str     # Must not exist
    new_password: str
    substation_id: str
    substation_location: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    is_registered: bool

# --- HARDWARE ---

class FaultLogDisplay(BaseModel):
    id: int
    timestamp: datetime
    voltage: float
    current: float
    fault_type: str
    status: str
    
    class Config:
        from_attributes = True

# Input from Hardware/Simulator - 8 Features for ML Model
class HardwareInput(BaseModel):
    substation_id: str
    line_id: str
    
    # The 8 Features needed by your ML Model
    load_kw: float
    pf: float
    voltage_a: float
    voltage_b: float
    voltage_c: float
    current_a: float
    current_b: float
    current_c: float

# Manual input from dashboard - Phase A values only
class ManualGridInput(BaseModel):
    voltage_a: float        # Phase A Voltage (will be applied to all phases)
    current_a: float        # Phase A Current (will be applied to all phases)
    load_kw: float          # Load in kW
    power_factor: float     # Power factor (0.0 - 1.0)
    substation_id: str = "SUB-SIM-01"
    line_id: str = "FEEDER-05"

# --- DASHBOARD & MAP ---

class MapPin(BaseModel):
    substation_id: str
    location_name: str
    status: str
    lat: float
    lon: float
    google_maps_link: str


# --- HOUSEHOLD ELECTRICITY MANAGEMENT (SIMPLIFIED) ---

# Consumer registration - only needs meter_id, substation_id, email
class ConsumerCreate(BaseModel):
    meter_id: str
    substation_id: str
    email: Optional[str] = None

class ConsumerDisplay(BaseModel):
    id: int
    meter_id: str
    substation_id: str
    email: Optional[str]
    power_factor: float
    voltage: float
    trip_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Power reading input - meter_id, power_kw, voltage
class PowerReading(BaseModel):
    meter_id: str
    power_kw: float
    voltage: float
    power_factor: float

# Fault detection response
class FaultResponse(BaseModel):
    fault_type: Optional[str]  # "VOLTAGE_LOW", "PHASE_CHANGE", "TRIP", None
    message: str
    trip_count: int
    email_sent: bool
    
class TheftDetectionResponse(BaseModel):
    theft_detected: bool
    allocated_power: float
    total_consumer_power: float
    stolen_power: float
    status: str
