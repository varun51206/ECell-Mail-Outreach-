import sqlite3
import os
from backend.email_worker import send_email_smtp, get_campaign_attachment, get_db

def test():
    conn = get_db()
    row = conn.execute("SELECT sender_name, gmail_user, gmail_app_password FROM settings WHERE user_id = 1").fetchone()
    
    if not row:
        print("[Test] No settings found for user 1")
        conn.close()
        return

    gmail_user = row["gmail_user"]
    gmail_pass = row["gmail_app_password"]
    sender_name = row["sender_name"]

    # Check attachment
    attach_path, attach_name = get_campaign_attachment(conn, 1, "live_project")
    conn.close()

    print(f"[Test] Attachment path: {attach_path}")
    print(f"[Test] Attachment name: {attach_name}")
    if attach_path and os.path.exists(attach_path):
        print(f"[Test] Attachment file exists. Size: {os.path.getsize(attach_path)} bytes")

    to_email = "varunbhardwajxlily@gmail.com"
    subject = "Outreach OS Test Actual Send"
    body = "Hi Varun,\n\nThis is an actual send test checking SMTP connection disconnect reasons."

    print("[Test] Triggering send_email_smtp...")
    ok, msg = send_email_smtp(
        gmail_user=gmail_user,
        gmail_app_password=gmail_pass,
        to_email=to_email,
        subject=subject,
        body=body,
        from_name=sender_name,
        attachment_path=attach_path,
        attachment_name=attach_name
    )

    print(f"[Test] Result OK: {ok}")
    print(f"[Test] Message: {msg}")

if __name__ == "__main__":
    test()
