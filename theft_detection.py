from sqlalchemy.orm import Session
import models


def detect_theft(allocated_current: float, db: Session) -> dict:
    """
    Simple theft detection via current balance method.
    
    Sums all consumer currents and compares with allocated substation current.
    If sum > allocated, theft is detected on the transmission line.
    
    Args:
        allocated_current: Total current allocated to substation (e.g., 100A)
        db: Database session
    
    Returns:
        dict with theft_detected, allocated_current, total_consumer_current, 
        stolen_current, status, and consumers list
    """
    consumers = db.query(models.Consumer).all()
    total_consumer_current = 0.0
    consumer_list = []
    
    for consumer in consumers:
        # Get latest reading for this consumer
        latest_reading = db.query(models.ConsumptionHistory).filter(
            models.ConsumptionHistory.consumer_id == consumer.id
        ).order_by(models.ConsumptionHistory.timestamp.desc()).first()
        
        if latest_reading:
            total_consumer_current += latest_reading.current
            consumer_list.append({
                "meter_id": consumer.meter_id,
                "current": latest_reading.current,
                "address": consumer.address
            })
    
    # Calculate stolen current
    stolen_current = total_consumer_current - allocated_current
    theft_detected = stolen_current > 0
    
    return {
        "theft_detected": theft_detected,
        "allocated_current": allocated_current,
        "total_consumer_current": round(total_consumer_current, 2),
        "stolen_current": round(stolen_current, 2) if theft_detected else 0.0,
        "status": "THEFT_DETECTED" if theft_detected else "NORMAL",
        "consumers": consumer_list
    }
