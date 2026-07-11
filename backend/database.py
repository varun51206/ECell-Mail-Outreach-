import sqlite3
import hashlib
import os
import secrets
from datetime import datetime, timedelta

DB_DIR = "/data" if os.path.exists("/data") else os.path.dirname(__file__)
DB_PATH = os.path.join(DB_DIR, "ecell_outreach.db")

DEFAULT_TEMPLATES = {
    "live_project": {
        "initial_founder": {
            "subject": "A free consulting sprint for {{Company}} — from Ramjas's E-Cell",
            "body": """Hi {{FirstName}},

I run the Startup Edge, Ramjas College's E-Cell at Delhi University and I'll keep this short.

We run 4-12 week \"Live Projects\" where a small team of our students works on one real, well-scoped problem for a company: consumer research, GTM, a pitch deck, value-chain analysis, whatever's actually keeping you up at night this quarter. No fee. No fluff. Just a signed scope, a deadline, and a deliverable your team can actually use.

We've done this recently for Rapido (UX research feeding straight into their product roadmap), Bombay Shaving Company (Gen Z research that became 4 brand reels, 100K+ views), Findoc, Piramal Foundation, CRY, and a few others. Happy to send specifics.

What we ask in return: a completion certificate for the students, and honestly, your honest feedback.

If {{Company}} has a scoped problem sitting in a backlog somewhere, market sizing, a campus GTM push, a deck that needs a rebuild, I'd love 15 minutes this week to see if it's a fit.

Worth a quick call?

{{SenderName}}
President, The Startup Edge - E-Cell, Ramjas College, University of Delhi
{{SenderPhone}}""",
            "day_offset": 0
        },
        "initial_poc": {
            "subject": "16 colleges in 20 days, 100K+ views, one Rapido roadmap, {{Company}} could be next",
            "body": """Hi {{FirstName}},

Quick context before the ask: I lead The Startup Edge, the E-Cell at Ramjas College, University of Delhi. We run structured \"Live Projects\", student consulting teams embedded on a single, real business problem for 4-12 weeks.

A few recent outcomes:
- Rapido: field research with Captain-app drivers, delivered straight to their Product & Research heads as a roadmap input
- Bombay Shaving Company: Gen Z consumer research that directly shaped 4 brand reels (100K+ views)
- Zyber: scaled a campus rollout from 0 to 16 colleges and 1,000+ users in 20 days
- Piramal Foundation, Findoc, CRY, Poshn, Teach For India, United Way of Delhi - research, GTM, and strategy work across sectors

The deal is simple: no cost to you, a defined scope and timeline, C-suite-level delivery at the end, and in exchange, a certificate confirming the students worked under your team.

Open to a short call this week to see if there's a specific problem worth scoping?

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 0
        },
        "f1": {
            "subject": "Re: quick idea for {{Company}}",
            "body": """Hi {{FirstName}},

Just bumping this in case it got buried.

If useful, we can take one scoped problem off your team's plate for 4-12 weeks (no fee) and deliver a concrete output your team can use immediately.

Open to a 15-min call this week?

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 3
        },
        "f2": {
            "subject": "Re: free live project support for {{Company}}",
            "body": """Hi {{FirstName}},

Quick context on outcomes we've delivered:

- Rapido: field UX research used as roadmap input
- Bombay Shaving Company: Gen Z research shaping branded content
- Zyber: campus rollout support across 16 colleges in 20 days

Format is simple: one real problem, defined scope, fixed timeline, final deliverable.

Would you like us to suggest 2-3 possible problem statements for {{Company}}?

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 6
        },
        "f3": {
            "subject": "Re: should we propose a scoped sprint for {{Company}}?",
            "body": """Hi {{FirstName}},

To make this easy, here are projects we can execute quickly:

1) Consumer/market research sprint
2) Campus GTM pilot + feedback loop
3) Pitch deck / narrative rebuild
4) Competitor or value-chain analysis

If you share one priority area, I can send a one-page scope + timeline.

Worth exploring?

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 9
        },
        "f4": {
            "subject": "Re: close this thread?",
            "body": """Hi {{FirstName}},

I know inboxes are packed, so I'll keep this short.

If this isn't a priority right now, no worries — happy to close the loop.
If it is, I can send a draft scope for one problem area.

Should I close this for now?

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 12
        }
    },
    "pitch_deck": {
        "initial": {
            "subject": "Rebuilding {{Company}}'s pitch deck for fundraising",
            "body": """Hi {{FirstName}},

I lead the Fundraising Support Wing at the Startup Edge, Ramjas College. We help high-growth startups structure, design, and refine their investor presentations and financial models.

We run a dedicated 3-week fundraising cohort where our team works directly with founders to:
1. Deconstruct the narrative (ensuring the problem-solution fit, market sizing, and traction stand out to institutional VCs).
2. Redesign the slides (clean, modern pitch deck design optimized for rapid investor scanning).
3. Draft cold outreach and investor FAQs.

We do this completely free of cost for select startups. We only ask for your feedback and a signed certificate of completion for our students.

Are you planning to raise funds or refresh your pitch deck in the coming quarters? I'd love to share 2-3 quick suggestions for {{Company}}'s deck.

Worth a brief call to see if it's a fit?

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 0
        },
        "f1": {
            "subject": "Re: {{Company}} pitch deck support",
            "body": """Hi {{FirstName}},

Bumping this. We can help you rebuild {{Company}}'s deck, polish the valuation slide, or build a clean financial model. 

If this is on your roadmap, we have a slot opening up next week. 

Let me know if we can coordinate a quick 10-minute call.

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 4
        },
        "f2": {
            "subject": "Re: free deck design slot for {{Company}}",
            "body": """Hi {{FirstName}},

Quick reference: here are a couple of examples of how we support founders:
- We redesign raw text slides into highly visual VC-ready formats.
- We run bottom-up TAM/SAM/SOM market sizing models.

Would you be open to sending over your current deck (or draft) for a quick, confidential review by our team? We'll send back 3 actionable improvements.

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 8
        }
    },
    "all_purpose": {
        "initial": {
            "subject": "Opportunity / Collaboration Proposal - {{Company}}",
            "body": """Hi {{FirstName}},

I hope you are doing well.

I am reaching out regarding a potential collaboration or opportunity with {{Company}}. I am highly interested in discussing how we can work together or support your team's initiatives.

Please find attached the file for your reference.

Would you be open to a brief conversation next week?

Best regards,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 0
        },
        "f1": {
            "subject": "Re: Collaboration Proposal - {{Company}}",
            "body": """Hi {{FirstName}},

Just wanted to follow up on my previous message. I understand you are busy, but I wanted to check if you had a moment to review the attached details.

I look forward to hearing from you.

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 3
        },
        "f2": {
            "subject": "Re: Collaboration Proposal - {{Company}}",
            "body": """Hi {{FirstName}},

I wanted to quickly follow up in case my previous mail got buried. I know you receive a lot of messages, so I'll keep this short.

If you have 10 minutes sometime next week, I'd love to connect and share more about how we can collaborate.

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 6
        },
        "f3": {
            "subject": "Re: Collaboration - {{Company}}",
            "body": """Hi {{FirstName}},

Just bumping this one last time in case it slipped through.

We'd love to explore how we can support {{Company}}'s initiatives or collaborate with your team this quarter.

Let me know if you are open to a brief call.

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 9
        },
        "f4": {
            "subject": "Re: closing this thread",
            "body": """Hi {{FirstName}},

I know you have a busy schedule, so I will close the loop on this thread for now.

If a collaboration or opportunity isn't a priority for {{Company}} at this time, no worries at all!

Feel free to drop a line if things open up in the future.

Best,
{{SenderName}}
{{SenderPhone}}""",
            "day_offset": 12
        }
    }
}


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # User table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")

    # Active login sessions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # User Settings / Signature
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER PRIMARY KEY,
        sender_name TEXT,
        sender_phone TEXT,
        gmail_user TEXT,
        gmail_app_password TEXT,
        emergency_stop INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # Attachments locker (supports individual campaigns)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        campaign_id TEXT NOT NULL, -- 'live_project', 'pitch_deck', 'all_purpose'
        file_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # Templates table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS templates (
        user_id INTEGER NOT NULL,
        campaign_id TEXT NOT NULL,
        step_key TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        day_offset INTEGER NOT NULL,
        PRIMARY KEY (user_id, campaign_id, step_key),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    # Leads and schedule queue
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schedule (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        campaign_id TEXT NOT NULL,
        email TEXT NOT NULL,
        first_name TEXT,
        company TEXT,
        role TEXT,
        custom_field_1 TEXT, -- flexible field (e.g. resume filename, specific topic)
        custom_field_2 TEXT,
        status TEXT NOT NULL DEFAULT 'Pending', -- 'Pending', 'Sent', 'Replied', 'Call Booked', 'Closed', 'Failed'
        stage_step TEXT NOT NULL, -- 'initial', 'f1', 'f2', etc.
        scheduled_date TEXT NOT NULL,
        last_sent_at TEXT,
        notes TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")

    conn.commit()

    # Column migrations for open and click tracking
    try:
        cursor.execute("ALTER TABLE schedule ADD COLUMN open_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE schedule ADD COLUMN click_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN public_url TEXT DEFAULT 'http://127.0.0.1:8000'")
    except sqlite3.OperationalError:
        pass
    conn.commit()

    # Seed default templates for all registered users if they are missing
    users = cursor.execute("SELECT id FROM users").fetchall()
    for u in users:
        u_id = u["id"]
        for campaign_id, steps in DEFAULT_TEMPLATES.items():
            for step_key, data in steps.items():
                cursor.execute("""
                    INSERT OR IGNORE INTO templates (user_id, campaign_id, step_key, subject, body, day_offset)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (u_id, campaign_id, step_key, data["subject"], data["body"], data["day_offset"]))
    conn.commit()
    conn.close()


def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return hashed, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    hashed, _ = hash_password(password, salt)
    return hmac_compare(hashed, password_hash)


def hmac_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


def create_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    try:
        password_hash, salt = hash_password(password)
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username.strip().lower(), password_hash, salt, now)
        )
        user_id = cursor.lastrowid

        # Insert default settings
        cursor.execute(
            "INSERT INTO settings (user_id, sender_name, sender_phone, gmail_user, gmail_app_password, emergency_stop) VALUES (?, ?, ?, ?, ?, 0)",
            (user_id, username, "", "", "")
        )

        # Seed default templates for this user
        for campaign_id, steps in DEFAULT_TEMPLATES.items():
            for step_key, data in steps.items():
                cursor.execute("""
                    INSERT INTO templates (user_id, campaign_id, step_key, subject, body, day_offset)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (user_id, campaign_id, step_key, data["subject"], data["body"], data["day_offset"]))

        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    expires_at = (datetime.now() + timedelta(days=7)).isoformat()
    conn = get_db()
    conn.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at)
    )
    conn.commit()
    conn.close()
    return token


def get_user_from_session(token: str):
    if not token:
        return None
    conn = get_db()
    row = conn.execute("""
        SELECT u.id, u.username
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ? AND s.expires_at > ?
    """, (token, datetime.now().isoformat())).fetchone()
    conn.close()
    if row:
        return {"id": row["id"], "username": row["username"]}
    return None


def destroy_session(token: str):
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# Database initialization run
if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
