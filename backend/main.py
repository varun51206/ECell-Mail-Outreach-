import os
import shutil
import sqlite3
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr

from backend.database import get_db, init_db, create_user, create_session, get_user_from_session, destroy_session
from backend.email_worker import get_user_sending_state, start_sending_thread, send_email_smtp

app = FastAPI(title="E-Cell Outreach OS API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants & Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ATTACH_DIR = os.path.join(BASE_DIR, "attachments")
os.makedirs(ATTACH_DIR, exist_ok=True)

# Background worker configuration is now manual per user


# Pydantic Schemas
class UserAuth(BaseModel):
    username: str
    password: str

class SmtpSettings(BaseModel):
    sender_name: str
    sender_phone: str
    gmail_user: str
    gmail_app_password: str

class TestSmtpRequest(BaseModel):
    recipient_email: str

class TemplateUpdate(BaseModel):
    campaign_id: str
    step_key: str
    subject: str
    body: str
    day_offset: int

class LeadItem(BaseModel):
    email: EmailStr
    first_name: Optional[str] = ""
    company: Optional[str] = ""
    role: Optional[str] = ""
    custom_field_1: Optional[str] = ""
    custom_field_2: Optional[str] = ""
    start_from: Optional[str] = "initial"

class BulkLeadUpload(BaseModel):
    campaign_id: str
    leads: List[LeadItem]
    start_date: str  # YYYY-MM-DD
    offsets: dict    # e.g., {"initial": 0, "f1": 3, "f2": 6, ...}
    replace_mode: bool

class StatusUpdate(BaseModel):
    email: str
    campaign_id: str
    status: str      # 'Replied', 'Call Booked', 'Closed', 'Pending'
    notes: Optional[str] = ""


# Dependency: Authenticate User via Token in Authorization Header
async def get_current_user(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token is missing"
        )
    # Support 'Bearer <token>' or raw token
    token = authorization.replace("Bearer ", "").strip()
    user = get_user_from_session(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid"
        )
    return user


# --- Auth Routes ---

@app.post("/api/register")
def register(auth: UserAuth):
    if not auth.username or len(auth.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if not auth.password or len(auth.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    user_id = create_user(auth.username, auth.password)
    if not user_id:
        raise HTTPException(status_code=400, detail="Username is already taken")
    return {"message": "User registered successfully"}

@app.post("/api/login")
def login(auth: UserAuth):
    conn = get_db()
    row = conn.execute(
        "SELECT id, password_hash, salt FROM users WHERE username = ?",
        (auth.username.strip().lower(),)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    # Hash the input password to check match
    import hashlib
    hashed = hashlib.sha256((auth.password + row["salt"]).encode("utf-8")).hexdigest()
    if hashed != row["password_hash"]:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    token = create_session(row["id"])
    return {"token": token, "username": auth.username}

@app.post("/api/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        destroy_session(token)
    return {"message": "Logged out successfully"}

@app.get("/api/me")
def me(user = Depends(get_current_user)):
    return user


# --- Settings & SMTP ---

@app.get("/api/settings")
def fetch_settings(user = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute("""
        SELECT sender_name, sender_phone, gmail_user, gmail_app_password, emergency_stop 
        FROM settings WHERE user_id = ?
    """, (user["id"],)).fetchone()
    conn.close()
    
    if not row:
        return {"sender_name": "", "sender_phone": "", "gmail_user": "", "gmail_app_password": "", "emergency_stop": 0}
    
    return {
        "sender_name": row["sender_name"] or "",
        "sender_phone": row["sender_phone"] or "",
        "gmail_user": row["gmail_user"] or "",
        # Mask password for security when fetching
        "gmail_app_password": row["gmail_app_password"] or "",
        "emergency_stop": bool(row["emergency_stop"])
    }

@app.post("/api/settings")
def save_settings(settings_data: SmtpSettings, user = Depends(get_current_user)):
    conn = get_db()
    conn.execute("""
        UPDATE settings 
        SET sender_name = ?, sender_phone = ?, gmail_user = ?, gmail_app_password = ?
        WHERE user_id = ?
    """, (settings_data.sender_name, settings_data.sender_phone, 
          settings_data.gmail_user.strip(), settings_data.gmail_app_password.strip(), user["id"]))
    conn.commit()
    conn.close()
    return {"message": "Settings updated successfully"}

@app.post("/api/settings/toggle-stop")
def toggle_stop(user = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute("SELECT emergency_stop FROM settings WHERE user_id = ?", (user["id"],)).fetchone()
    current = row["emergency_stop"] if row else 0
    new_state = 1 if current == 0 else 0
    conn.execute("UPDATE settings SET emergency_stop = ? WHERE user_id = ?", (new_state, user["id"]))
    conn.commit()
    conn.close()
    return {"emergency_stop": bool(new_state)}

@app.post("/api/settings/test-smtp")
def test_smtp(req: TestSmtpRequest, user = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute("SELECT sender_name, gmail_user, gmail_app_password FROM settings WHERE user_id = ?", (user["id"],)).fetchone()
    conn.close()

    if not row or not row["gmail_user"] or not row["gmail_app_password"]:
        raise HTTPException(status_code=400, detail="Configure Gmail SMTP details first")

    ok, msg = send_email_smtp(
        gmail_user=row["gmail_user"],
        gmail_app_password=row["gmail_app_password"],
        to_email=req.recipient_email,
        subject="SMTP Outreach Test Message",
        body=f"Hello,\n\nThis is a test email sent from E-Cell Outreach OS settings page.\nYour SMTP settings are working perfectly!\n\nBest,\n{row['sender_name']}",
        from_name=row["sender_name"] or "E-Cell Mailer"
    )

    if not ok:
        raise HTTPException(status_code=400, detail=f"SMTP test failed: {msg}")
    return {"message": "Test email sent successfully"}


# --- Attachments ---

@app.post("/api/attachments/upload")
async def upload_attachment(
    campaign_id: str = Form(...),
    file: UploadFile = File(...),
    user = Depends(get_current_user)
):
    if campaign_id not in ["live_project", "pitch_deck", "all_purpose"]:
        raise HTTPException(status_code=400, detail="Invalid campaign ID")

    # Create safe file path
    ext = os.path.splitext(file.filename)[1]
    safe_name = f"user_{user['id']}_{campaign_id}{ext}"
    dest_path = os.path.join(ATTACH_DIR, safe_name)

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    conn = get_db()
    # Check if user already uploaded attachment for this campaign. If so, overwrite it in the table
    row = conn.execute("SELECT id FROM attachments WHERE user_id = ? AND campaign_id = ?", (user["id"], campaign_id)).fetchone()
    now_ts = datetime.now().isoformat()
    if row:
        conn.execute("""
            UPDATE attachments SET file_path = ?, file_name = ?, uploaded_at = ? WHERE id = ?
        """, (dest_path, file.filename, now_ts, row["id"]))
    else:
        conn.execute("""
            INSERT INTO attachments (user_id, campaign_id, file_path, file_name, uploaded_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user["id"], campaign_id, dest_path, file.filename, now_ts))
    conn.commit()
    conn.close()

    return {"filename": file.filename, "campaign_id": campaign_id}

@app.get("/api/attachments")
def list_attachments(user = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute("SELECT campaign_id, file_name, uploaded_at FROM attachments WHERE user_id = ?", (user["id"],)).fetchall()
    conn.close()
    return [{"campaign_id": r["campaign_id"], "file_name": r["file_name"], "uploaded_at": r["uploaded_at"]} for r in rows]

@app.delete("/api/attachments/{campaign_id}")
def delete_attachment(campaign_id: str, user = Depends(get_current_user)):
    conn = get_db()
    row = conn.execute("SELECT file_path FROM attachments WHERE user_id = ? AND campaign_id = ?", (user["id"], campaign_id)).fetchone()
    if row:
        if os.path.exists(row["file_path"]):
            try:
                os.remove(row["file_path"])
            except OSError:
                pass
        conn.execute("DELETE FROM attachments WHERE user_id = ? AND campaign_id = ?", (user["id"], campaign_id))
        conn.commit()
    conn.close()
    return {"message": "Attachment deleted"}


# --- Templates ---

@app.get("/api/templates")
def fetch_templates(user = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute("""
        SELECT campaign_id, step_key, subject, body, day_offset 
        FROM templates WHERE user_id = ?
    """, (user["id"],)).fetchall()
    conn.close()
    
    res = {}
    for r in rows:
        c_id = r["campaign_id"]
        if c_id not in res:
            res[c_id] = {}
        res[c_id][r["step_key"]] = {
            "subject": r["subject"],
            "body": r["body"],
            "day_offset": r["day_offset"]
        }
    return res

@app.post("/api/templates/save")
def save_template(data: TemplateUpdate, user = Depends(get_current_user)):
    conn = get_db()
    conn.execute("""
        INSERT INTO templates (user_id, campaign_id, step_key, subject, body, day_offset)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, campaign_id, step_key) 
        DO UPDATE SET subject=excluded.subject, body=excluded.body, day_offset=excluded.day_offset
    """, (user["id"], data.campaign_id, data.step_key, data.subject, data.body, data.day_offset))
    conn.commit()
    conn.close()
    return {"message": "Template saved successfully"}


# --- Leads & Scheduling Grid ---

@app.get("/api/schedule")
def get_schedule(campaign_id: str, user = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute("""
        SELECT id, email, first_name, company, role, custom_field_1, custom_field_2, 
               status, stage_step, scheduled_date, last_sent_at, notes
        FROM schedule 
        WHERE user_id = ? AND campaign_id = ?
        ORDER BY id ASC
    """, (user["id"], campaign_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/schedule/bulk")
def schedule_bulk_leads(payload: BulkLeadUpload, user = Depends(get_current_user)):
    if not payload.leads:
        raise HTTPException(status_code=400, detail="Leads list cannot be empty")
        
    start_dt = datetime.strptime(payload.start_date, "%Y-%m-%d")
    
    conn = get_db()
    cursor = conn.cursor()
    
    if payload.replace_mode:
        cursor.execute("DELETE FROM schedule WHERE user_id = ? AND campaign_id = ?", (user["id"], payload.campaign_id))
    
    now_ts = datetime.now().isoformat()
    
    # Define steps configuration based on campaign category
    if payload.campaign_id == "live_project":
        generic_steps = ["initial", "f1", "f2", "f3", "f4"]
        template_keys = {
            "initial": "initial_founder",
            "f1": "f1",
            "f2": "f2",
            "f3": "f3",
            "f4": "f4"
        }
    elif payload.campaign_id == "pitch_deck":
        generic_steps = ["initial", "f1", "f2"]
        template_keys = {
            "initial": "initial",
            "f1": "f1",
            "f2": "f2"
        }
    else:
        generic_steps = ["initial", "f1", "f2", "f3", "f4"]
        template_keys = {
            "initial": "initial",
            "f1": "f1",
            "f2": "f2",
            "f3": "f3",
            "f4": "f4"
        }

    # Fetch templates offsets for these steps
    steps = []
    for step in generic_steps:
        db_key = template_keys[step]
        row = cursor.execute("""
            SELECT day_offset FROM templates 
            WHERE user_id = ? AND campaign_id = ? AND step_key = ?
        """, (user["id"], payload.campaign_id, db_key)).fetchone()
        
        # Determine offset
        offset = row["day_offset"] if row else 0
        if step in payload.offsets:
            offset = payload.offsets[step]
        
        steps.append((step, int(offset)))
        
    steps.sort(key=lambda x: x[1])

    if not steps:
        raise HTTPException(status_code=400, detail="No email template stages configured for this campaign.")

    for lead in payload.leads:
        start_step = lead.start_from or "initial"
        if start_step not in generic_steps:
            start_step = "initial"
            
        start_index = generic_steps.index(start_step)
        
        starting_offset = 0
        for step, offset in steps:
            if step == start_step:
                starting_offset = offset
                break
                
        for step_key, offset in steps:
            if generic_steps.index(step_key) < start_index:
                continue
                
            adjusted_offset = offset - starting_offset
            scheduled_date = (start_dt + timedelta(days=adjusted_offset)).date().isoformat()
            
            cursor.execute("""
                INSERT INTO schedule (
                    user_id, campaign_id, email, first_name, company, role, 
                    custom_field_1, custom_field_2, status, stage_step, 
                    scheduled_date, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?, ?, '', ?)
            """, (
                user["id"], payload.campaign_id, lead.email.strip(), lead.first_name, 
                lead.company, lead.role, lead.custom_field_1, lead.custom_field_2,
                step_key, scheduled_date, now_ts
            ))
            
    conn.commit()
    conn.close()
    return {"message": f"Successfully scheduled {len(payload.leads) * len(steps)} emails for {len(payload.leads)} leads"}

@app.post("/api/schedule/update-status")
def update_status(data: StatusUpdate, user = Depends(get_current_user)):
    conn = get_db()
    
    # Update status for ALL pending/sent records of this specific lead email within the current user's campaign
    conn.execute("""
        UPDATE schedule 
        SET status = ?, notes = CASE WHEN ? != '' THEN ? ELSE notes END
        WHERE user_id = ? AND campaign_id = ? AND email = ?
    """, (data.status, data.notes, data.notes, user["id"], data.campaign_id, data.email.strip()))
    
    conn.commit()
    conn.close()
    return {"message": f"Updated status of {data.email} to {data.status}"}

@app.post("/api/schedule/clear")
def clear_schedule(campaign_id: str, user = Depends(get_current_user)):
    conn = get_db()
    conn.execute("DELETE FROM schedule WHERE user_id = ? AND campaign_id = ?", (user["id"], campaign_id))
    conn.commit()
    conn.close()
    return {"message": f"Outreach queue for campaign '{campaign_id}' has been cleared"}

@app.get("/api/schedule/stats")
def get_stats(user = Depends(get_current_user)):
    conn = get_db()
    rows = conn.execute("""
        SELECT campaign_id, status, COUNT(*) as count 
        FROM schedule 
        WHERE user_id = ? 
        GROUP BY campaign_id, status
    """, (user["id"],)).fetchall()
    conn.close()
    
    stats = {}
    for r in rows:
        c_id = r["campaign_id"]
        status_val = r["status"]
        count = r["count"]
        if c_id not in stats:
            stats[c_id] = {"Pending": 0, "Sent": 0, "Replied": 0, "Call Booked": 0, "Closed": 0, "Failed": 0}
        stats[c_id][status_val] = count
    return stats


@app.post("/api/schedule/send")
def trigger_sending(user = Depends(get_current_user)):
    started = start_sending_thread(user["id"])
    if not started:
        raise HTTPException(status_code=400, detail="Emails are already being sent.")
    return {"message": "Email sending batch started in the background."}

@app.get("/api/schedule/send-status")
def get_sending_status(user = Depends(get_current_user)):
    return get_user_sending_state(user["id"])


# Serve Frontend static files
frontend_path = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    def read_root():
        return {"message": "API running. Create frontend folder to serve the web application interface."}


# Initialize DB when main runs
init_db()
