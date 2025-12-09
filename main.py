import secrets
import random
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
import models, database, schemas, auth, ai_engine, notifications, simulation
import serial_bridge
from datetime import datetime, timezone, timedelta
import household_analyzer

models.Base.metadata.create_all(bind=database.engine)
app = FastAPI(title="KSEB Smart Grid")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL LIVE CACHE ---
live_grid_state = {
    "voltage": 0.0,
    "current": 0.0,
    "status": "WAITING",
    "last_updated": datetime.utcnow()
}

manual_command_queue = None


# ============================================================================
# 1. AUTHENTICATION FLOW
# ============================================================================

@app.post("/admin/create-temp-credentials")
def create_temp_user(req: schemas.TempUserCreate, db: Session = Depends(database.get_db)):
    """
    IT Admin generates random UserID & Password for Officer.
    """
    temp_id = f"OFFICER-{secrets.token_hex(2).upper()}"
    temp_pass = secrets.token_hex(3)
    
    new_user = models.User(
        userid=temp_id,
        hashed_password=auth.get_password_hash(temp_pass),
        role=req.role,
        is_registered=False
    )
    db.add(new_user)
    db.commit()
    return {"userid": temp_id, "password": temp_pass}

@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    user = db.query(models.User).filter(models.User.userid == form_data.username).first()
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect credentials")
    
    token = auth.create_access_token(data={"sub": user.userid})
    return {
        "access_token": token, 
        "token_type": "bearer", 
        "role": user.role, 
        "is_registered": user.is_registered
    }

@app.post("/register")
def register(
    form: schemas.RegistrationForm, 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(database.get_db)
):
    try:
        if not current_user:
            raise HTTPException(status_code=401, detail="Invalid Session")

        if current_user.is_registered:
            return {"msg": "Already registered"}
        
        taken_user = db.query(models.User).filter(models.User.userid == form.new_userid).first()
        if taken_user:
            raise HTTPException(status_code=400, detail="New UserID already exists")

        user_in_db = db.query(models.User).filter(models.User.id == current_user.id).first()
        
        if not user_in_db:
            raise HTTPException(status_code=404, detail="User record lost")

        user_in_db.first_name = form.first_name
        user_in_db.last_name = form.last_name
        user_in_db.phone_number = form.phone_number
        user_in_db.email = form.email
        user_in_db.substation_id = form.substation_id
        user_in_db.substation_location = form.substation_location
        user_in_db.userid = form.new_userid
        user_in_db.hashed_password = auth.get_password_hash(form.new_password)
        user_in_db.is_registered = True
        
        db.commit()
        db.refresh(user_in_db)
        
        return {"msg": "Registration Complete. Please login with new credentials."}

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"❌ REGISTER ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")


# ============================================================================
# 2. DASHBOARD & MAP
# ============================================================================

@app.get("/api/dashboard")
def get_dashboard(user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    logs = db.query(models.FaultLog).order_by(models.FaultLog.timestamp.desc()).limit(20).all()
    
    return {
        "current_reading": live_grid_state["current"],
        "voltage_reading": live_grid_state["voltage"],
        "grid_status": live_grid_state["status"],
        "last_updated": live_grid_state["last_updated"].isoformat(),
        "logs": logs
    }

@app.get("/api/map", response_model=list[schemas.MapPin])
def get_map_pins(user: models.User = Depends(auth.get_current_user)):
    lat = 9.93
    lon = 76.2673
    gmap_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    
    return [{
        "substation_id": user.substation_id or "SUB-01",
        "location_name": user.substation_location or "Kochi",
        "status": "ACTIVE",
        "lat": lat,
        "lon": lon,
        "google_maps_link": gmap_link
    }]


# ============================================================================
# 3. HARDWARE CONTROL
# ============================================================================

@app.post("/api/input-grid-data")
def input_grid_data(manual_input: schemas.ManualGridInput, user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    global manual_command_queue, live_grid_state
    
    hardware_data = schemas.HardwareInput(
        substation_id=manual_input.substation_id,
        line_id=manual_input.line_id,
        load_kw=manual_input.load_kw,
        pf=manual_input.power_factor,
        voltage_a=manual_input.voltage_a,
        voltage_b=manual_input.voltage_a,
        voltage_c=manual_input.voltage_a,
        current_a=manual_input.current_a,
        current_b=manual_input.current_a,
        current_c=manual_input.current_a
    )
    
    result = receive_data(hardware_data, db)
    
    return {
        **result,
        "input_source": "manual_dashboard",
        "message": f"Data processed from dashboard input by {user.userid}"
    }

@app.post("/hardware/data")
def receive_data(data: schemas.HardwareInput, db: Session = Depends(database.get_db)):
    global manual_command_queue, live_grid_state
    
    is_fault, fault_msg, voltage = ai_engine.analyze_data(data)
    
    live_grid_state["voltage"] = voltage
    live_grid_state["current"] = data.current_a
    live_grid_state["last_updated"] = datetime.now(timezone.utc)

    command_to_send = "CONTINUE"

    if manual_command_queue:
        print(f"⚠️ EXECUTING MANUAL COMMAND: {manual_command_queue}")
        command_to_send = manual_command_queue
        
        if command_to_send == "TRIP":
            live_grid_state["status"] = "MANUAL_TRIP"
        elif command_to_send == "RESET":
            live_grid_state["status"] = "STABLE"
            
        manual_command_queue = None 
        return {"command": command_to_send, "reason": "Manual Override"}

    if is_fault:
        live_grid_state["status"] = "CRITICAL"
        print(f"🚨 FAULT DETECTED: {fault_msg}")
        
        log = models.FaultLog(
            substation_id=data.substation_id, line_id=data.line_id,
            voltage=voltage, current=data.current_a, 
            fault_type=fault_msg, status="Active"
        )
        db.add(log)
        db.commit()
        
        notifications.send_alert("9988776655", "officer@kseb.in", fault_msg, data.current_a, voltage)
        
        command_to_send = "TRIP"
    else:
        if live_grid_state["status"] == "CRITICAL":
            live_grid_state["status"] = "STABLE"
            
        command_to_send = "CONTINUE"

    return {"command": command_to_send, "reason": fault_msg}

@app.post("/api/control/{action}")
def manual_control(action: str, user: models.User = Depends(auth.get_current_user)):
    global manual_command_queue
    
    if action.upper() not in ["TRIP", "RESET"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use TRIP or RESET.")
    
    manual_command_queue = action.upper()
    print(f"🛑 MANUAL COMMAND QUEUED: {action} by {user.userid}")
    
    return {
        "status": "Queued", 
        "action": action, 
        "message": "Command will be sent on next heartbeat."
    }


# ============================================================================
# 4. HOUSEHOLD ELECTRICITY MANAGEMENT - 3 FEATURES ONLY
# ============================================================================

@app.post("/api/consumer/register")
def register_consumer(
    consumer_data: schemas.ConsumerCreate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Register a new household consumer.
    Required: meter_id, substation_id, email (optional)
    """
    
    if not user or not user.is_registered:
        raise HTTPException(status_code=403, detail="User must be registered to register consumers")
    
    # Check if meter_id already exists
    existing = db.query(models.Consumer).filter(
        models.Consumer.meter_id == consumer_data.meter_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Meter ID already registered")
    
    # Create consumer
    new_consumer = models.Consumer(
        meter_id=consumer_data.meter_id,
        substation_id=consumer_data.substation_id,
        email=consumer_data.email,
        power_factor=0.0,
        voltage=0.0,
        trip_count=0
    )
    
    db.add(new_consumer)
    db.commit()
    db.refresh(new_consumer)
    
    return {
        "status": "registered",
        "consumer_id": new_consumer.id,
        "meter_id": new_consumer.meter_id,
        "substation_id": new_consumer.substation_id,
        "message": "Consumer registered successfully"
    }


@app.post("/api/consumer/reading")
def record_power_reading(
    reading: schemas.PowerReading,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    FEATURE 1 & 2: Record power reading and check for trip/voltage faults.
    
    Trip Logic: If power_kw > threshold_power, increment trip_count by 1
    Email: When trip_count reaches 5, send email to consumer
    
    Voltage Faults:
    - voltage < 130V: "VOLTAGE_LOW" popup
    - voltage 130-180V: "PHASE_CHANGE" popup
    """
    
    # Find consumer by meter_id
    consumer = db.query(models.Consumer).filter(
        models.Consumer.meter_id == reading.meter_id
    ).first()
    
    if not consumer:
        raise HTTPException(status_code=404, detail="Meter not found")
    
    # Define threshold power for this substation (e.g., 5kW)
    THRESHOLD_POWER = 5.0
    TRIP_LIMIT = 5  # Email sent when trip_count reaches this
    
    # Check if power exceeds threshold
    trip_occurred = reading.power_kw > THRESHOLD_POWER
    
    if trip_occurred:
        consumer.trip_count += 1
    
    # Update consumer readings
    consumer.power_factor = reading.power_factor
    consumer.voltage = reading.voltage
    db.commit()
    db.refresh(consumer)
    
    # Determine fault type based on voltage
    fault_type = None
    message = "Normal operation"
    
    if reading.voltage < 130:
        fault_type = "VOLTAGE_LOW"
        message = "⚠️ VOLTAGE FLUCTUATION: Voltage below 130V detected"
    elif 130 <= reading.voltage <= 180:
        fault_type = "PHASE_CHANGE"
        message = "⚠️ PHASE CHANGE: Voltage between 130-180V (phase change detected)"
    
    # If trip count reaches limit, send email
    email_sent = False
    if consumer.trip_count >= TRIP_LIMIT and consumer.email:
        email_sent = household_analyzer.send_threshold_increase_email(
            consumer_email=consumer.email,
            consumer_name=f"Meter {consumer.meter_id}",
            trip_count=consumer.trip_count
        )
    
    return {
        "status": "recorded",
        "consumer_id": consumer.id,
        "meter_id": consumer.meter_id,
        "trip_count": consumer.trip_count,
        "trip_occurred": trip_occurred,
        "power_kw": reading.power_kw,
        "voltage": reading.voltage,
        "power_factor": reading.power_factor,
        "fault_type": fault_type,
        "fault_message": message,
        "email_sent": email_sent,
        "email_threshold_reached": consumer.trip_count >= TRIP_LIMIT
    }


@app.get("/api/theft/detect")
def detect_theft(
    power_transmission: float,
    substation_id: str,
    phase: str = "A",
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    FEATURE 3: Theft Detection on LT Phase
    
    Compares power transmission on a phase with sum of house consumption on that phase.
    
    Logic:
    - Get actual power transmitted on this phase (from substation)
    - Sum all consumer power consumption on this phase
    - If sum < transmission: Extra power is being consumed (POWER THEFT)
    
    The difference = unauthorized power consumption on that phase
    
    Parameters:
    - power_transmission: Actual power being transmitted on the phase (float, kW)
    - substation_id: Substation identifier (string)
    - phase: Phase letter "A", "B", or "C" (default "A")
    """
    
    # Get all consumers in this substation
    consumers = db.query(models.Consumer).filter(
        models.Consumer.substation_id == substation_id
    ).all()
    
    if not consumers:
        return {
            "theft_detected": False,
            "power_transmission": power_transmission,
            "total_consumer_power": 0.0,
            "unauthorized_power": 0.0,
            "status": "NO_CONSUMERS",
            "message": "No consumers found in this substation",
            "phase": phase
        }
    
    # Sum all consumer power consumption
    total_consumer_power = sum(c.power_factor if c.power_factor else 0.0 for c in consumers)
    
    # Calculate unauthorized (stolen) power
    # If transmission > sum of houses: difference is stolen power
    unauthorized_power = power_transmission - total_consumer_power
    theft_detected = unauthorized_power > 0
    
    status = "THEFT_DETECTED" if theft_detected else "NORMAL"
    message = (
        f"🚨 PHASE {phase}: POWER THEFT DETECTED! "
        f"{unauthorized_power:.2f} kW unauthorized consumption"
    ) if theft_detected else "Normal operation"
    
    result = {
        "theft_detected": theft_detected,
        "phase": phase,
        "power_transmission": power_transmission,
        "total_consumer_power": round(total_consumer_power, 2),
        "unauthorized_power": round(unauthorized_power, 2) if theft_detected else 0.0,
        "status": status,
        "message": message,
        "consumers_count": len(consumers),
        "substation_id": substation_id,
        "detection_logic": "If transmission > sum(consumer_power) then theft exists"
    }
    
    return result

