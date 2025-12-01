import secrets
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import models, database, schemas, auth, ai_engine, simulation   

# 1. Setup
models.Base.metadata.create_all(bind=database.engine)
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    simulation.start()

# --- 1. IT DEPT: Create Temporary Credentials ---
@app.post("/admin/create-temp-user")
def create_temp_user(req: schemas.InviteRequest, db: Session = Depends(auth.get_db)):
    """
    Generates a Random UserID and Password.
    Give these to the Officer on a slip of paper.
    """
    # Generate random credentials
    temp_username = f"{req.role.upper()}-{secrets.token_hex(2).upper()}"
    temp_password = secrets.token_hex(4) # e.g., "8f3a1b2c"
    
    hashed = auth.get_password_hash(temp_password)
    
    new_user = models.User(
        username=temp_username,
        hashed_password=hashed,
        role=req.role,
        is_registered=False  # Important! This triggers the redirect.
    )
    db.add(new_user)
    db.commit()
    
    return {
        "msg": "Temporary Credentials Created. Give these to the officer.",
        "temp_username": temp_username,
        "temp_password": temp_password
    }

# --- 2. COMMON: Login ---
@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(auth.get_db)):
    """
    Used by BOTH Admin and Unregistered Officers.
    """
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    token = auth.create_access_token(data={"sub": user.username})
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "is_registered": user.is_registered # Frontend checks this!
    }

# --- 3. OFFICER: Complete Registration ---
@app.post("/complete-registration")
def complete_registration(
    form: schemas.CompleteRegistration,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(auth.get_db)
):
    # 1. Validation
    if current_user.is_registered:
        return {"msg": "You are already registered!"}

    existing = db.query(models.User).filter(models.User.username == form.new_username).first()
    if existing:
        raise HTTPException(status_code=400, detail="New Username is already taken")

    print(f"DEBUG: Updating User {current_user.username} to {form.new_username}")

    try:
        # 2. THE FIX: Merge the user into the current session
        # This creates a copy of 'current_user' that belongs to 'db' (Session B)
        user_to_update = db.merge(current_user)

        # 3. Update the NEW object (user_to_update), NOT the old one (current_user)
        user_to_update.username = form.new_username
        user_to_update.hashed_password = auth.get_password_hash(form.new_password)
        user_to_update.first_name = form.first_name
        user_to_update.last_name = form.last_name
        user_to_update.substation_location = form.substation_location
        user_to_update.substation_id = form.substation_id
        user_to_update.phone_number = form.phone_number
        user_to_update.email = form.email
        user_to_update.is_registered = True 
        
        # 4. Commit
        db.commit()
        print("DEBUG: Database updated successfully")
        
        return {"msg": "Registration Complete. Please login with your new details."}

    except Exception as e:
        print(f"ERROR SAVING TO DB: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

# --- 4. DASHBOARD (Only for Registered Users) ---
@app.get("/api/dashboard")
def get_dashboard(user: models.User = Depends(auth.get_current_user), db: Session = Depends(auth.get_db)):
    
    if not user.is_registered:
        raise HTTPException(status_code=403, detail="Please complete registration first")
    
    logs = db.query(models.FaultLog).order_by(models.FaultLog.timestamp.desc()).limit(20).all()
    latest = logs[0] if logs else None
    status = "CRITICAL" if (latest and latest.status == "Active") else "STABLE"
        
    return {
        "user": user.username,
        "grid_status": status,
        "logs": logs
    }

# --- 5. HARDWARE SIMULATION ROUTE ---
@app.post("/hardware/telemetry")
def receive_telemetry(data: schemas.TelemetryData, db: Session = Depends(auth.get_db)):
    is_fault, fault_type, conf = ai_engine.analyze_signal(data.voltage, data.current, data.noise)
    
    if is_fault:
        new_log = models.FaultLog(
            box_id=data.box_id, line_id=data.line_id, voltage=data.voltage,
            current=data.current, noise_level=data.noise, fault_type=fault_type, status="Active"
        )
        db.add(new_log)
        db.commit()
        return {"command": "TRIP_CIRCUIT"}
    return {"command": "CONTINUE"}