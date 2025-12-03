def send_alert(phone, email, fault_msg, current, voltage):
    print(f"\n[📲 SMS SENT] To: {phone} | MSG: {fault_msg}. I={current}A V={voltage}V")
    print(f"[📧 EMAIL SENT] To: {email} | MSG: Recommend Immediate Inspection.\n")