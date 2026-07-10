import sqlite3
import smtplib
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ecell_outreach.db")

def test():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT sender_name, gmail_user, gmail_app_password FROM settings WHERE user_id = 1").fetchone()
    conn.close()

    if not row:
        print("[Test] No settings found for user_id = 1")
        return

    gmail_user = row["gmail_user"]
    gmail_pass = row["gmail_app_password"]

    print(f"[Test] Using Gmail user: '{gmail_user}'")
    print(f"[Test] App Password length: {len(gmail_pass) if gmail_pass else 0} chars")

    if not gmail_user or not gmail_pass:
        print("[Test] Username or password is empty")
        return

    try:
        print("[Test] Connecting to smtp.gmail.com:587...")
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        
        print("[Test] Sending EHLO...")
        print(server.ehlo())
        
        print("[Test] Starting TLS...")
        print(server.starttls())
        
        print("[Test] Sending EHLO after TLS...")
        print(server.ehlo())
        
        print("[Test] Attempting login...")
        print(server.login(gmail_user.strip(), gmail_pass.strip()))
        
        print("[Test] Login SUCCESSFUL!")
        server.quit()
    except Exception as e:
        print(f"[Test FAILURE] Stage failed: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    test()
