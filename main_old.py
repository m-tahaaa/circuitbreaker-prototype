import secrets
import random
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
import models, database, schemas, auth, ai_engine, notifications, simulation, theft_detection
import serial_bridge
from datetime import datetime, timezone, timedelta
import household_analyzer as household_analyzer
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
# Stores the latest reading in RAM. Updates instantly.
# This allows the dashboard to show live numbers even if there is no fault.
live_grid_state = {
    "voltage": 0.0,
    "current": 0.0,
    "status": "WAITING",
    "last_updated": datetime.utcnow()
}

# Stores manual commands (TRIP/RESET) until Arduino polls for them
manual_command_queue = None
# @app.on_event("startup")
# def startup():
#     simulation.start() # Hardware Simulator
#     #print("🔌 Starting Serial Bridge for Real Arduino...")
#     #serial_bridge.start()

# --- 1. AUTHENTICATION FLOW ---

@app.post("/admin/create-temp-credentials")
def create_temp_user(req: schemas.TempUserCreate, db: Session = Depends(database.get_db)):
    """
    IT Admin generates random UserID & Password for Officer.
    """
    temp_id = f"OFFICER-{secrets.token_hex(2).upper()}"
    temp_pass = secrets.token_hex(3) # e.g. "a1b2c3"
    
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
    print(f"DEBUG: Starting registration for {form.new_userid}")
    
    try:
        # 1. Check if current user is valid
        if not current_user:
            print("DEBUG: No current user found")
            raise HTTPException(status_code=401, detail="Invalid Session")

        if current_user.is_registered:
            print("DEBUG: User already registered")
            return {"msg": "Already registered"}
        
        # 2. Check if NEW UserID is taken
        taken_user = db.query(models.User).filter(models.User.userid == form.new_userid).first()
        if taken_user:
            print(f"DEBUG: UserID {form.new_userid} is taken")
            raise HTTPException(status_code=400, detail="New UserID already exists")

        # 3. FETCH FRESH USER (The Session Fix)
        # We use the ID to get a clean object attached to the current DB session
        user_in_db = db.query(models.User).filter(models.User.id == current_user.id).first()
        
        if not user_in_db:
            print("DEBUG: User record missing in DB")
            raise HTTPException(status_code=404, detail="User record lost")

        # 4. UPDATE FIELDS
        print("DEBUG: Updating fields...")
        user_in_db.first_name = form.first_name
        user_in_db.last_name = form.last_name
        user_in_db.phone_number = form.phone_number
        user_in_db.email = form.email
        user_in_db.substation_id = form.substation_id
        user_in_db.substation_location = form.substation_location
        
        # 5. SWAP CREDENTIALS
        print("DEBUG: Hashing password...")
        user_in_db.userid = form.new_userid
        user_in_db.hashed_password = auth.get_password_hash(form.new_password)
        user_in_db.is_registered = True
        
        # 6. SAVE
        print("DEBUG: Committing to DB...")
        db.commit()
        db.refresh(user_in_db)
        print("DEBUG: Success!")
        
        return {"msg": "Registration Complete. Please login with new credentials."}

    except HTTPException as he:
        raise he # Re-raise expected errors
    except Exception as e:
        # This prints the real crash reason to your terminal
        print(f"❌ CRITICAL REGISTER ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

    except Exception as e:
        print(f"❌ REGISTER ERROR: {e}")
        # This print will show up in your VS Code terminal if it fails again
        raise HTTPException(status_code=500, detail=f"Server Error: {str(e)}")

# --- 2. DASHBOARD & MAP ---

@app.get("/api/dashboard")
def get_dashboard(user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    # 1. Fetch Historical Logs (From Database)
    logs = db.query(models.FaultLog).order_by(models.FaultLog.timestamp.desc()).limit(20).all()
    
    # 2. Fetch Live Data (From Memory Cache)
    # This allows the dashboard to show "0.5 A" even if we didn't save it to the DB
    return {
        "current_reading": live_grid_state["current"],
        "voltage_reading": live_grid_state["voltage"],
        "grid_status": live_grid_state["status"],
        "last_updated": live_grid_state["last_updated"].isoformat(),
        "logs": logs,
        "manual_input_endpoint": "/api/input-grid-data",
        "manual_input_description": "POST request with voltage_a, current_a, load_kw, power_factor"
    }

@app.get("/api/map", response_model=list[schemas.MapPin])
def get_map_pins(user: models.User = Depends(auth.get_current_user)):
    # In real app, fetch from DB. For demo, we hardcode the substation location.
    lat = 9.93
    lon = 76.2673
    gmap_link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    
    return [{
        "substation_id": user.substation_id or "SUB-01",
        "location_name": user.substation_location or "Kochi",
        "status": "ACTIVE FAULT", # Logic to check if fault exists
        "lat": lat,
        "lon": lon,
        "google_maps_link": gmap_link
    }]

# --- 3. HARDWARE CONTROL ---
# The Bridge calls this every 1 second
# --- HARDWARE DATA INGESTION ---

# User can manually input grid data from dashboard
@app.post("/api/input-grid-data")
def input_grid_data(manual_input: schemas.ManualGridInput, user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    global manual_command_queue, live_grid_state
    
    # Convert manual input to HardwareInput format
    # Phase A values are used for all phases (B and C)
    hardware_data = schemas.HardwareInput(
        substation_id=manual_input.substation_id,
        line_id=manual_input.line_id,
        load_kw=manual_input.load_kw,
        pf=manual_input.power_factor,
        voltage_a=manual_input.voltage_a,
        voltage_b=manual_input.voltage_a,  # Same as Phase A
        voltage_c=manual_input.voltage_a,  # Same as Phase A
        current_a=manual_input.current_a,
        current_b=manual_input.current_a,  # Same as Phase A
        current_c=manual_input.current_a   # Same as Phase A
    )
    
    # Process through the same AI engine
    result = receive_data(hardware_data, db)
    
    return {
        **result,
        "input_source": "manual_dashboard",
        "message": f"Data processed from dashboard input by {user.userid}"
    }

@app.post("/hardware/data")
def receive_data(data: schemas.HardwareInput, db: Session = Depends(database.get_db)):
    global manual_command_queue, live_grid_state
    
    # 1. Run AI Analysis
    is_fault, fault_msg, voltage = ai_engine.analyze_data(data)
    
    # Update Live Cache
    live_grid_state["voltage"] = voltage
    live_grid_state["current"] = data.current_a
    live_grid_state["last_updated"] = datetime.now(timezone.utc)

    command_to_send = "CONTINUE"

    # --- PRIORITY 1: MANUAL OVERRIDE (RESET/TRIP) ---
    if manual_command_queue:
        print(f"⚠️ EXECUTING MANUAL COMMAND: {manual_command_queue}")
        command_to_send = manual_command_queue
        
        if command_to_send == "TRIP":
            live_grid_state["status"] = "MANUAL_TRIP"
        elif command_to_send == "RESET":
            live_grid_state["status"] = "STABLE"
            
        manual_command_queue = None 
        return {"command": command_to_send, "reason": "Manual Override"}

    # --- PRIORITY 2: REAL-TIME FAULT DETECTION ---
    # No Latch. Logic is purely based on current sensor reading.
    
    if is_fault:
        live_grid_state["status"] = "CRITICAL"
        print(f"🚨 FAULT DETECTED: {fault_msg}")
        
        # Log to DB
        log = models.FaultLog(
            substation_id=data.substation_id, line_id=data.line_id,
            voltage=voltage, current=data.current_a, 
            fault_type=fault_msg, status="Active"
        )
        db.add(log)
        db.commit()
        
        # Send Alert
        notifications.send_alert("9988776655", "officer@kseb.in", fault_msg, data.current_a, voltage)
        
        command_to_send = "TRIP"
    else:
        # If AI says Normal, we go back to STABLE immediately
        # (Unless we are in a Manual Trip state, which we usually preserve)
        if live_grid_state["status"] == "CRITICAL":
            live_grid_state["status"] = "STABLE"
            
        command_to_send = "CONTINUE"

    return {"command": command_to_send, "reason": fault_msg}

# The User (Frontend) calls this
@app.post("/api/control/{action}")
def manual_control(action: str, user: models.User = Depends(auth.get_current_user)):
    global manual_command_queue
    
    # Validate Input
    if action.upper() not in ["TRIP", "RESET"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use TRIP or RESET.")
    
    # Queue the command for the next Arduino heartbeat
    manual_command_queue = action.upper()
    print(f"🛑 MANUAL COMMAND QUEUED: {action} by {user.userid}")
    
    return {
        "status": "Queued", 
        "action": action, 
        "message": "Command will be sent on next heartbeat."
    }


# --- 4. HOUSEHOLD ELECTRICITY MANAGEMENT ---

import household_analyzer as household_analyzer

@app.post("/api/consumer/register")
def register_consumer(
    consumer_data: schemas.ConsumerCreate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Consumer registers their household in the system.
    Any authenticated user can register consumers.
    """
    
    # Allow any authenticated user to register consumers
    if not user or not user.is_registered:
        raise HTTPException(status_code=403, detail="User must be registered to register consumers")
    
    # Check if meter_id already exists
    existing = db.query(models.Consumer).filter(
        models.Consumer.meter_id == consumer_data.meter_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Meter ID already registered")
    
    # Create consumer record
    new_consumer = models.Consumer(
        user_id=user.id,
        meter_id=consumer_data.meter_id,
        address=consumer_data.address,
        email=consumer_data.email,
        latitude=consumer_data.latitude,
        longitude=consumer_data.longitude,
        connected_appliances=str(consumer_data.connected_appliances),
        estimated_max_consumption_kw=consumer_data.estimated_max_consumption_kw,
        distance_from_transformer=consumer_data.distance_from_transformer
    )
    
    db.add(new_consumer)
    db.commit()
    db.refresh(new_consumer)
    
    # Create default thresholds for all 24 hours
    for hour in range(24):
        threshold = models.ConsumerThreshold(
            consumer_id=new_consumer.id,
            hour_of_day=hour,
            voltage_min=190,
            voltage_max=240,
            current_max=16
        )
        db.add(threshold)
    
    db.commit()
    
    return {
        "status": "success",
        "consumer_id": new_consumer.id,
        "meter_id": consumer_data.meter_id,
        "message": "Consumer registered successfully"
    }


@app.post("/api/consumer/consumption")
def record_consumption(
    reading: schemas.ConsumptionReading,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Record consumption reading for a household meter.
    Automatically checks all fault conditions.
    """
    
    # Find consumer by meter_id
    consumer = db.query(models.Consumer).filter(
        models.Consumer.meter_id == reading.meter_id
    ).first()
    
    if not consumer:
        raise HTTPException(status_code=404, detail="Meter not found")
    
    # Get current thresholds for this hour
    current_hour = datetime.now().hour
    threshold = db.query(models.ConsumerThreshold).filter(
        models.ConsumerThreshold.consumer_id == consumer.id,
        models.ConsumerThreshold.hour_of_day == current_hour
    ).first()
    
    if not threshold:
        threshold = db.query(models.ConsumerThreshold).filter(
            models.ConsumerThreshold.consumer_id == consumer.id
        ).first()
    
    # Determine if trip occurred
    trip_count = 0
    trip_reason = None
    
    # If power consumption > 5kW, increment trip count
    if reading.power_kw > 5:
        trip_count += 1
        trip_reason = "HIGH_POWER_CONSUMPTION"
    
    if reading.voltage > threshold.voltage_max:
        trip_count += 1
        trip_reason = "OVERVOLTAGE"
    elif reading.voltage < threshold.voltage_min:
        trip_count += 1
        trip_reason = "UNDERVOLTAGE"
    
    if reading.current > threshold.current_max:
        trip_count += 1
        trip_reason = "OVERCURRENT"
    
    # Record consumption
    consumption_history = models.ConsumptionHistory(
        consumer_id=consumer.id,
        voltage=reading.voltage,
        current=reading.current,
        power_kw=reading.power_kw,
        power_factor=reading.power_factor,
        trip_count=trip_count,
        trip_reason=trip_reason
    )
    
    db.add(consumption_history)
    db.commit()
    db.refresh(consumption_history)
    
    response = {
        "status": "recorded",
        "consumer_id": consumer.id,
        "meter_id": reading.meter_id,
        "trip_count": trip_count,
        "trip_reason": trip_reason
    }
    
    # If trip occurred, send alert
    if trip_count > 0:
        user_obj = db.query(models.User).filter(models.User.id == consumer.user_id).first()
        if user_obj:
            notifications.send_alert(
                user_obj.phone_number,
                user_obj.email,
                f"Circuit Trip Alert - {trip_reason}",
                reading.current,
                f"Your circuit tripped at {reading.voltage}V, {reading.current}A. Trip Count: {trip_count}"
            )
    
    # Get total trip count for this consumer from all history
    total_trips = db.query(func.sum(models.ConsumptionHistory.trip_count)).filter(
        models.ConsumptionHistory.consumer_id == consumer.id
    ).scalar() or 0
    total_trips += trip_count
    
    # If trip count > 10, send email to consumer asking to increase threshold voltage
    if total_trips > 10 and consumer.email:
        household_analyzer.send_threshold_increase_email(
            consumer_email=consumer.email,
            consumer_name=consumer.address,
            trip_count=int(total_trips)
        )
    
    return response


@app.get("/api/consumer/{consumer_id}/health")
def get_consumer_health(
    consumer_id: int,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Get comprehensive health report for a consumer.
    Runs all 4 fault detection algorithms:
    1. Time-based threshold patterns
    2. Voltage drop detection
    3. Theft detection
    4. Voltage fluctuation detection
    """
    
    # Verify consumer exists
    consumer = db.query(models.Consumer).filter(models.Consumer.id == consumer_id).first()
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")
    
    # Run integrated analysis
    health_report = household_analyzer.analyze_consumer_health(consumer_id, db)
    
    return health_report


@app.get("/api/consumer/{consumer_id}/dashboard")
def get_consumer_dashboard(
    consumer_id: int,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Get consumer dashboard with:
    - Current consumption data
    - Trip history
    - Detected fault patterns
    - Current thresholds by hour
    - Health score
    """
    
    consumer = db.query(models.Consumer).filter(models.Consumer.id == consumer_id).first()
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")
    
    # Get consumer info
    consumer_info = {
        "id": consumer.id,
        "meter_id": consumer.meter_id,
        "address": consumer.address,
        "estimated_max_consumption_kw": consumer.estimated_max_consumption_kw
    }
    
    # Get latest reading
    latest_reading = db.query(models.ConsumptionHistory).filter(
        models.ConsumptionHistory.consumer_id == consumer_id
    ).order_by(models.ConsumptionHistory.timestamp.desc()).first()
    
    current_reading = {
        "timestamp": latest_reading.timestamp,
        "voltage": latest_reading.voltage,
        "current": latest_reading.current,
        "power_kw": latest_reading.power_kw,
        "power_factor": latest_reading.power_factor
    } if latest_reading else None
    
    # Get today's trip count
    today_readings = db.query(models.ConsumptionHistory).filter(
        models.ConsumptionHistory.consumer_id == consumer_id,
        models.ConsumptionHistory.timestamp >= datetime.now().replace(hour=0, minute=0, second=0)
    ).all()
    
    trip_count_today = sum(r.trip_count for r in today_readings)
    
    # Get hourly consumption stats
    hourly_stats = {}
    for hour in range(24):
        hour_readings = [r for r in today_readings if r.timestamp.hour == hour]
        
        if hour_readings:
            hourly_stats[f"{hour:02d}:00"] = {
                "avg_power_kw": sum(r.power_kw for r in hour_readings) / len(hour_readings),
                "avg_voltage": sum(r.voltage for r in hour_readings) / len(hour_readings),
                "trip_count": sum(r.trip_count for r in hour_readings)
            }
    
    # Get current thresholds
    current_hour = datetime.now().hour
    current_thresholds = db.query(models.ConsumerThreshold).filter(
        models.ConsumerThreshold.consumer_id == consumer_id
    ).all()
    
    thresholds_display = [
        {
            "hour": t.hour_of_day,
            "voltage_min": t.voltage_min,
            "voltage_max": t.voltage_max,
            "current_max": t.current_max
        }
        for t in current_thresholds
    ]
    
    # Get health score
    health = household_analyzer.analyze_consumer_health(consumer_id, db)
    
    return {
        "consumer_info": consumer_info,
        "current_reading": current_reading,
        "trip_count_today": trip_count_today,
        "hourly_consumption_stats": hourly_stats,
        "current_thresholds": thresholds_display,
        "health_score": health["health_score"],
        "health_status": health["health_status"],
        "detected_faults": health["detected_faults"]
    }


@app.post("/api/consumer/{consumer_id}/adjust-threshold")
def adjust_threshold(
    consumer_id: int,
    adjustment: schemas.ThresholdUpdate,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Officer or consumer adjusts threshold for a specific hour.
    This is the recommended action when time-based patterns are detected.
    """
    
    consumer = db.query(models.Consumer).filter(models.Consumer.id == consumer_id).first()
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")
    
    # Update threshold
    threshold = db.query(models.ConsumerThreshold).filter(
        models.ConsumerThreshold.consumer_id == consumer_id,
        models.ConsumerThreshold.hour_of_day == adjustment.hour_of_day
    ).first()
    
    if not threshold:
        threshold = models.ConsumerThreshold(
            consumer_id=consumer_id,
            hour_of_day=adjustment.hour_of_day,
            voltage_min=adjustment.voltage_min,
            voltage_max=adjustment.voltage_max,
            current_max=adjustment.current_max
        )
    else:
        threshold.voltage_min = adjustment.voltage_min
        threshold.voltage_max = adjustment.voltage_max
        threshold.current_max = adjustment.current_max
        threshold.last_adjusted = datetime.utcnow()
        threshold.adjusted_count += 1
    
    db.add(threshold)
    db.commit()
    
    # Send notification to consumer
    user_obj = db.query(models.User).filter(models.User.id == consumer.user_id).first()
    if user_obj:
        time_str = f"{adjustment.hour_of_day:02d}:00"
        notifications.send_alert(
            user_obj.phone_number,
            user_obj.email,
            f"Threshold Updated for {time_str}",
            adjustment.voltage_max,
            f"Your voltage threshold has been adjusted: {adjustment.voltage_min}V - {adjustment.voltage_max}V"
        )
    
    return {
        "status": "success",
        "hour": adjustment.hour_of_day,
        "new_voltage_min": adjustment.voltage_min,
        "new_voltage_max": adjustment.voltage_max,
        "new_current_max": adjustment.current_max,
        "message": "Threshold adjusted successfully"
    }


@app.get("/api/consumer/{consumer_id}/consumption-stats")
def get_consumption_stats(
    consumer_id: int,
    days: int = 30,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Get consumption statistics for a consumer over N days.
    Shows peak hours, off-peak hours, and patterns.
    """
    
    consumer = db.query(models.Consumer).filter(models.Consumer.id == consumer_id).first()
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")
    
    # Get readings for specified period
    cutoff_date = datetime.now() - timedelta(days=days)
    readings = db.query(models.ConsumptionHistory).filter(
        models.ConsumptionHistory.consumer_id == consumer_id,
        models.ConsumptionHistory.timestamp >= cutoff_date
    ).all()
    
    if not readings:
        return {
            "consumer_id": consumer_id,
            "period_days": days,
            "data_points": 0,
            "message": "No consumption data for this period"
        }
    
    # Calculate statistics
    hourly_data = {}
    daily_data = {}
    
    for reading in readings:
        hour = reading.timestamp.hour
        day = reading.timestamp.date()
        
        if hour not in hourly_data:
            hourly_data[hour] = []
        hourly_data[hour].append(reading.power_kw)
        
        if day not in daily_data:
            daily_data[day] = []
        daily_data[day].append(reading.power_kw)
    
    # Compute hourly averages
    hourly_avg = {h: sum(vals) / len(vals) for h, vals in hourly_data.items()}
    peak_hours = sorted(hourly_avg.items(), key=lambda x: x[1], reverse=True)[:3]
    off_peak_hours = sorted(hourly_avg.items(), key=lambda x: x[1])[:3]
    
    # Compute daily total
    daily_totals = {str(day): sum(vals) / len(vals) for day, vals in daily_data.items()}
    monthly_total = sum(sum(vals) for vals in daily_data.values())
    
    return {
        "consumer_id": consumer_id,
        "meter_id": consumer.meter_id,
        "period_days": days,
        "data_points": len(readings),
        "hourly_average": hourly_avg,
        "peak_hours": [{"hour": h, "avg_kw": v} for h, v in peak_hours],
        "off_peak_hours": [{"hour": h, "avg_kw": v} for h, v in off_peak_hours],
        "daily_totals": daily_totals,
        "monthly_total_kwh": monthly_total,
        "average_daily_consumption": monthly_total / days if days > 0 else 0
    }


@app.post("/api/climate-alert")
def send_climate_alert(
    alert: schemas.ClimateAlert,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Officer sends climate-based alert to consumers.
    Helps prepare for weather-related faults.
    """
    
    if user.role != "officer":
        raise HTTPException(status_code=403, detail="Only officers can send climate alerts")
    
    consumer = db.query(models.Consumer).filter(
        models.Consumer.meter_id == alert.meter_id
    ).first()
    
    if not consumer:
        raise HTTPException(status_code=404, detail="Consumer not found")
    
    # Log the climate alert
    climate_fault = models.ClimateFaultLog(
        consumer_id=consumer.id,
        weather_condition=alert.weather_condition,
        temperature=alert.temperature,
        humidity=alert.humidity,
        fault_description=f"{alert.weather_condition} - {alert.expected_impact}",
        severity="HIGH"
    )
    
    db.add(climate_fault)
    db.commit()
    
    # Send notification to consumer
    user_obj = db.query(models.User).filter(models.User.id == consumer.user_id).first()
    if user_obj:
        notifications.send_alert(
            user_obj.phone_number,
            user_obj.email,
            f"Weather Alert: {alert.weather_condition}",
            alert.temperature or 0,
            f"Weather: {alert.weather_condition}\nAction: {alert.recommended_action}"
        )
    
    return {
        "status": "alert_sent",
        "consumer_id": consumer.id,
        "weather_condition": alert.weather_condition,
        "recommended_action": alert.recommended_action,
        "message": "Consumer has been notified"
    }


# --- 5. SUBSTATION-LEVEL THEFT DETECTION ---

@app.get("/api/theft/substation-report")
def get_substation_theft_report(
    allocated_current: float = 100.0,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Detect theft on transmission line.
    
    Compares:
    - Allocated substation current (fixed value, e.g., 100A)
    - Sum of all consumer currents
    
    If sum > allocated: THEFT DETECTED
    If theft detected: Mark entire transmission line
    
    Query params:
    - allocated_current: Total current allocated to substation (default 100A)
    """
    
    if user.role != "officer":
        raise HTTPException(status_code=403, detail="Only officers can view theft reports")
    
    # Run simple theft detection
    result = theft_detection.detect_theft(allocated_current, db)
    
    return result


@app.get("/api/theft/detect")
def detect_theft_by_current_balance(
    allocated_current: float = 100.0,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Quick theft detection check.
    
    Returns theft status if theft detected.
    """
    
    if user.role != "officer":
        raise HTTPException(status_code=403, detail="Only officers can check for theft")
    
    result = theft_detection.detect_theft(allocated_current, db)
    
    return result


@app.get("/api/theft/alert")
def mark_transmission_line_for_theft(
    allocated_current: float = 100.0,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Check if theft is detected on transmission line.
    If theft detected: mark entire transmission line.
    
    Returns:
    {
        "theft_detected": bool,
        "allocated_current": float,
        "total_consumer_current": float,
        "stolen_current": float,
        "status": "THEFT_DETECTED" or "NORMAL",
        "consumers": list of all houses and their currents
    }
    """
    
    if user.role != "officer":
        raise HTTPException(status_code=403, detail="Only officers can check for theft")
    
    result = theft_detection.detect_theft(allocated_current, db)
    
    if result["theft_detected"]:
        # Log the alert
        fault = models.FaultPatternAnalysis(
            consumer_id=None,  # Transmission line level, not consumer level
            fault_type="TRANSMISSION_LINE_THEFT",
            description=f"Theft detected: {result['stolen_current']:.2f}A stolen out of {allocated_current}A allocated",
            confidence=0.95,
            recommended_action="INSPECT_TRANSMISSION_LINE",
            action_status="PENDING"
        )
        db.add(fault)
        db.commit()
    
    return result

