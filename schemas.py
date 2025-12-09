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

# Input from Arduino (Current Only)
class HardwareInput(BaseModel):
    substation_id: str
    line_id: str
    current: float 
    voltage: float        # <--- Added this
    noise_level: float = 0.0 # Optional now
# --- DASHBOARD & MAP ---

class FaultLogDisplay(BaseModel):
    id: int
    timestamp: datetime
    voltage: float
    current: float
    fault_type: str
    status: str
    
    class Config:
        from_attributes = True

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

class MapPin(BaseModel):
    substation_id: str
    location_name: str
    status: str
    lat: float
    lon: float
    google_maps_link: str