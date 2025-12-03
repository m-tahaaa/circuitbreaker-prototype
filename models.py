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