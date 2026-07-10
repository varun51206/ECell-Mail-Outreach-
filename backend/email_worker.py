import time
import os
import sqlite3
import threading
from datetime import datetime
import smtplib
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from backend.database import get_db, DB_PATH

STOP_STATUSES = ["Replied", "Call Booked", "Closed"]

# Global dict to store sending state per user
# user_id -> { is_sending: bool, sent_count: int, total_to_send: int, current_log: str }
sending_states = {}
states_lock = threading.Lock()

def sanitize_template_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    replacements = {
        "{{First Name}}": "{{FirstName}}", "{{First_Name}}": "{{FirstName}}", "{{first_name}}": "{{FirstName}}",
        "{{Company Name}}": "{{Company}}", "{{Problem Area}}": "{{ProblemArea}}",
        "{{Sender Name}}": "{{SenderName}}", "{{Sender Phone}}": "{{SenderPhone}}",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text

def render_template(text: str, data: dict) -> str:
    out = sanitize_template_text(text)
    for k, v in data.items():
        out = out.replace(f"{{{{{k}}}}}", str(v if v is not None else ""))
    return out

def get_campaign_attachment(conn, user_id, campaign_id):
    row = conn.execute("""
        SELECT file_path, file_name 
        FROM attachments 
        WHERE user_id = ? AND campaign_id = ? 
        ORDER BY id DESC LIMIT 1
    """, (user_id, campaign_id)).fetchone()
    if row:
        return row["file_path"], row["file_name"]
    return None, None

def send_email_smtp(gmail_user, gmail_app_password, to_email, subject, body, from_name,
                     attachment_path="", attachment_name=""):
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{gmail_user}>"
        msg["To"] = to_email.strip()
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            name = attachment_name or os.path.basename(attachment_path)
            part.add_header("Content-Disposition", f'attachment; filename="{name}"')
            msg.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=180) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_user.strip(), gmail_app_password.strip())
            server.sendmail(gmail_user.strip(), [to_email.strip()], msg.as_string())
        return True, "Sent successfully"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)}"

def get_user_sending_state(user_id: int):
    with states_lock:
        if user_id not in sending_states:
            sending_states[user_id] = {
                "is_sending": False,
                "sent_count": 0,
                "total_to_send": 0,
                "current_log": "Idle"
            }
        return sending_states[user_id].copy()

def set_user_sending_state(user_id: int, is_sending: bool, sent_count: int, total_to_send: int, current_log: str):
    with states_lock:
        sending_states[user_id] = {
            "is_sending": is_sending,
            "sent_count": sent_count,
            "total_to_send": total_to_send,
            "current_log": current_log
        }

def process_due_emails(user_id: int):
    # Initialize state
    set_user_sending_state(user_id, True, 0, 0, "Querying due emails...")

    conn = get_db()
    today = datetime.now().date().isoformat()
    placeholders = ",".join(["?"] * len(STOP_STATUSES))
    
    # Query due rows strictly for this user_id
    query = f"""
        SELECT s.id, s.user_id, s.campaign_id, s.email, s.first_name, s.company, s.role,
               s.custom_field_1, s.custom_field_2, s.stage_step,
               u.sender_name, u.sender_phone, u.gmail_user, u.gmail_app_password, u.emergency_stop
        FROM schedule s
        JOIN settings u ON s.user_id = u.user_id
        WHERE s.user_id = ?
          AND s.scheduled_date <= ?
          AND s.status = 'Pending'
          AND u.emergency_stop = 0
          AND s.email NOT IN (
              SELECT email FROM schedule 
              WHERE status IN ({placeholders}) AND user_id = s.user_id AND campaign_id = s.campaign_id
          )
        ORDER BY s.scheduled_date ASC, s.id ASC
    """
    
    try:
        rows = conn.execute(query, (user_id, today, *STOP_STATUSES)).fetchall()
    except sqlite3.OperationalError as e:
        err_msg = f"Database Error: {e}"
        print(f"[Worker] {err_msg}")
        set_user_sending_state(user_id, False, 0, 0, err_msg)
        conn.close()
        return

    total_count = len(rows)
    if total_count == 0:
        set_user_sending_state(user_id, False, 0, 0, "No pending emails scheduled for today.")
        conn.close()
        return

    set_user_sending_state(user_id, True, 0, total_count, f"Found {total_count} emails to send. Starting batch...")
    
    templates_cache = {}
    sent_count = 0

    try:
        for row in rows:
            # Check dynamic emergency stop before sending each email
            chk = conn.execute("SELECT emergency_stop FROM settings WHERE user_id = ?", (user_id,)).fetchone()
            if chk and chk["emergency_stop"]:
                log_msg = "Sending paused. Emergency Stop activated."
                print(f"[Worker] {log_msg}")
                set_user_sending_state(user_id, False, sent_count, total_count, log_msg)
                break

            row_id = row["id"]
            campaign_id = row["campaign_id"]
            to_email = row["email"]
            first_name = row["first_name"]
            company = row["company"]
            role = row["role"]
            c1 = row["custom_field_1"]
            c2 = row["custom_field_2"]
            stage_step = row["stage_step"]
            sender_name = row["sender_name"]
            sender_phone = row["sender_phone"]
            gmail_user = row["gmail_user"]
            gmail_app_password = row["gmail_app_password"]

            sent_count += 1
            set_user_sending_state(user_id, True, sent_count, total_count, f"Sending to {to_email} ({sent_count}/{total_count})...")

            # Validate credentials
            if not gmail_user or not gmail_app_password:
                conn.execute("UPDATE schedule SET status='Failed', notes='Missing SMTP credentials in settings.' WHERE id=?", (row_id,))
                conn.commit()
                continue

            # Fetch template details
            resolved_step = stage_step
            if campaign_id == "live_project" and stage_step == "initial":
                segment = str(c2 or "poc").strip().lower()
                resolved_step = "initial_founder" if "founder" in segment else "initial_poc"

            template_key = f"{user_id}_{campaign_id}_{resolved_step}"
            if template_key not in templates_cache:
                t_row = conn.execute("""
                    SELECT subject, body FROM templates 
                    WHERE user_id = ? AND campaign_id = ? AND step_key = ?
                """, (user_id, campaign_id, resolved_step)).fetchone()
                if t_row:
                    templates_cache[template_key] = (t_row["subject"], t_row["body"])
                else:
                    templates_cache[template_key] = None

            template_data = templates_cache[template_key]
            if not template_data:
                conn.execute("UPDATE schedule SET status='Failed', notes='Template not found for this step.' WHERE id=?", (row_id,))
                conn.commit()
                continue

            subject_template, body_template = template_data

            # Render variables
            data_bindings = {
                "FirstName": first_name or "",
                "Company": company or "",
                "Role": role or "",
                "Custom1": c1 or "",
                "Custom2": c2 or "",
                "SenderName": sender_name or "Your Name",
                "SenderPhone": sender_phone or "",
            }
            
            subject = render_template(subject_template, data_bindings)
            body = render_template(body_template, data_bindings)

            # Attachments are only sent on 'initial' stage
            attach_path, attach_name = "", ""
            if stage_step == "initial":
                attach_path, attach_name = get_campaign_attachment(conn, user_id, campaign_id)

            # Send SMTP Email
            ok, msg = send_email_smtp(
                gmail_user=gmail_user,
                gmail_app_password=gmail_app_password,
                to_email=to_email,
                subject=subject,
                body=body,
                from_name=sender_name or "Your Name",
                attachment_path=attach_path,
                attachment_name=attach_name
            )

            # Update Database
            status_val = "Sent" if ok else "Failed"
            sent_ts = datetime.now().isoformat()
            conn.execute("""
                UPDATE schedule 
                SET status = ?, last_sent_at = ?, notes = ? 
                WHERE id = ?
            """, (status_val, sent_ts, msg, row_id))
            conn.commit()
            
            print(f"[Worker] User {user_id} | Campaign {campaign_id} | Sent to {to_email} | Result: {msg}")

            # 5-6 second cooldown (5.5s) throttle delay
            if sent_count < total_count:
                time.sleep(5.5)

        else:
            # Loop finished normally without break
            set_user_sending_state(user_id, False, sent_count, total_count, f"Batch complete! Successfully processed {sent_count} emails.")

    except Exception as ex:
        err_msg = f"Error during sending: {str(ex)}"
        print(f"[Worker] {err_msg}")
        set_user_sending_state(user_id, False, sent_count, total_count, err_msg)
    finally:
        conn.close()

def start_sending_thread(user_id: int):
    # Runs the process_due_emails function in a separate background thread
    state = get_user_sending_state(user_id)
    if state["is_sending"]:
        return False # Already sending

    t = threading.Thread(target=process_due_emails, args=(user_id,), daemon=True)
    t.start()
    return True
