from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # This serves as the Login ID
    userid = Column(String, unique=True, index=True) 
    hashed_password = Column(String)
    
    # Profile Fields (Filled during registration)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    substation_id = Column(String, nullable=True)      # e.g. "SUB-01"
    substation_location = Column(String, nullable=True) # e.g. "Kochi North"
    
    role = Column(String)  # 'admin' or 'officer'
    is_registered = Column(Boolean, default=False) # False = Temp Account

class FaultLog(Base):
    __tablename__ = "fault_logs"

    id = Column(Integer, primary_key=True, index=True)
    substation_id = Column(String, index=True)
    line_id = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Sensor Data
    voltage = Column(Float) # We will fill this with dummy values
    current = Column(Float) # From Arduino
    
    # Analysis
    fault_type = Column(String) # "HANGING", "OVERLOAD", "NORMAL"
    status = Column(String, default="Active") # "Active", "Resolved"


# --- HOUSEHOLD ELECTRICITY MANAGEMENT MODELS (SIMPLIFIED) ---

class Consumer(Base):
    """Household consumer - stores meter_id, substation_id, email, power_factor, voltage, trip_count"""
    __tablename__ = "consumers"
    
    id = Column(Integer, primary_key=True, index=True)
    meter_id = Column(String, unique=True, index=True)  # Unique meter number
    substation_id = Column(String, index=True)  # e.g. "SUB-01"
    email = Column(String, nullable=True)  # For notifications
    
    # Latest readings
    power_factor = Column(Float, default=0.0)
    voltage = Column(Float, default=0.0)
    trip_count = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
