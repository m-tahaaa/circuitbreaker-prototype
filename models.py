from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    
    # This serves as the Login ID (Temp ID initially, then New Username)
    username = Column(String, unique=True, index=True) 
    hashed_password = Column(String)
    
    # Status Flags
    role = Column(String)  # 'admin' or 'officer'
    is_registered = Column(Boolean, default=False) # False = Needs to register

    # Profile Fields (Nullable until registration)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    substation_location = Column(String, nullable=True)
    substation_id = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    email = Column(String, nullable=True)

class FaultLog(Base):
    __tablename__ = "fault_logs"
    id = Column(Integer, primary_key=True, index=True)
    box_id = Column(String, index=True)
    line_id = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    voltage = Column(Float)
    current = Column(Float)
    noise_level = Column(Float)
    fault_type = Column(String)
    status = Column(String, default="Active")