from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# 1. Admin uses this to create a temp user
class InviteRequest(BaseModel):
    role: str  # 'officer' or 'server_manager'

# 2. Officer uses this to complete registration
class CompleteRegistration(BaseModel):
    new_username: str
    new_password: str
    first_name: str
    last_name: str
    substation_location: str
    substation_id: str
    phone_number: str
    email: str

# 3. Login Response
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    is_registered: bool # Frontend uses this to redirect!

# 4. Hardware Data
class TelemetryData(BaseModel):
    box_id: str
    line_id: str
    voltage: float
    current: float
    noise: float