import secrets
import random
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import models, database, schemas, auth, ai_engine, notifications, simulation
import serial_bridge
from datetime import datetime, timezone

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

@app.on_event("startup")
def startup():
    #simulation.start() # Hardware Simulator
    print("🔌 Starting Serial Bridge for Real Arduino...")
    serial_bridge.start()

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
        "logs": logs
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

# Arduino Polling / Data Ingestion
# --- HARDWARE DATA INGESTION ---

@app.post("/hardware/data")
def receive_data(data: schemas.HardwareInput, db: Session = Depends(database.get_db)):
    global manual_command_queue, live_grid_state
    
    # 1. Run Logic (AI + Physics)
    # This detects if there is a fault, but we won't act on it yet.
    is_fault, fault_msg, voltage = ai_engine.analyze_data(data.current, data.voltage)
    
    # Update Live Cache (So Dashboard sees numbers)
    live_grid_state["voltage"] = voltage
    live_grid_state["current"] = data.current
    live_grid_state["last_updated"] = datetime.now(timezone.utc)

    command_to_send = "CONTINUE"

    # PRIORITY 1: AI Fault Detection (LOG ONLY, DO NOT TRIP)
    if is_fault:
        # We update status to CRITICAL so the Dashboard turns Red/Alerts user
        live_grid_state["status"] = "CRITICAL"
        
        # We Log it to DB (So history table updates)
        log = models.FaultLog(
            substation_id=data.substation_id, line_id=data.line_id,
            voltage=voltage, current=data.current,
            fault_type=fault_msg, status="Active"
        )
        db.add(log)
        db.commit()
        
        # We Send Alerts (SMS/Email)
        notifications.send_alert("9988776655", "officer@kseb.in", fault_msg, data.current, voltage)
        
        # NOTE: command_to_send stays "CONTINUE". 
        # The Arduino keeps running until a HUMAN sends "TRIP".

    # PRIORITY 2: Manual Override (The only way to move the motor)
    if manual_command_queue:
        print(f"⚠️ EXECUTING MANUAL COMMAND: {manual_command_queue}")
        command_to_send = manual_command_queue
        
        # Update status display based on manual command
        if command_to_send == "TRIP":
            live_grid_state["status"] = "MANUAL_TRIP"
        elif command_to_send == "RESET":
            live_grid_state["status"] = "STABLE"
            
        manual_command_queue = None # Clear queue after sending

    return {"command": command_to_send}

# Manual Control from Map (Resume/Stop)
# --- MANUAL CONTROL ENDPOINT ---

@app.post("/api/control/{action}")
def manual_control(action: str, user: models.User = Depends(auth.get_current_user)):
    global manual_command_queue
    
    # Validate Input
    if action not in ["TRIP", "RESET"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use TRIP or RESET.")
    
    # Queue the command for the next Arduino heartbeat
    manual_command_queue = action
    print(f"🛑 MANUAL COMMAND QUEUED: {action} by {user.userid}")
    
    return {"status": "Queued", "action": action, "message": "Command will be sent on next heartbeat."}