# E-Cell Outreach OS 🚀

A premium, self-contained multi-user web application designed for E-Cell society members to manage and automate highly personalized outreach campaigns. 

Written in **FastAPI (Python)** and styled with a custom modern **Forest Midnight & Emerald-Teal** CSS theme.

---

##  Features
1. **Multi-User Isolation**: Register and log in. Settings, SMTP credentials, templates, and lead queues are fully separated and private to your device.
2. **Three Campaign Streams**:
   - **Live Project Reachout**: Generic step sequences (Initial + 4 follow-ups) with automatic segment routing (Founder vs POC) and optional attachment support.
   - **Fundraising Pitch Decks**: Pitch deck and financial model review campaigns targeted at founders.
   - **All-Purpose Mailer**: A highly customizable mailer for HR resumes, guest invitations, or speaker outreach.
3. **Interactive Spreadsheet Lead Grid**: Type or paste your leads directly into the web grid. No CSV files or formatting required.
4. **Manual Send Trigger**: You have complete control. Press "Start Sending" to trigger the email batch manually, with a built-in **5.5-second cooldown** between messages to keep your Gmail account safe.
5. **Auto-Stop Logic**: If you mark a lead as `Replied`, `Closed`, or `Call Booked`, the app instantly stops all future scheduled follow-up emails for that address.
6. **Emergency Lockdown**: A global emergency red button to instantly freeze the sending queue if needed.

---

##  How to Run the App (For Team Members)

Follow these simple steps to download and run the application on your computer:

### Step 1: Download the Project
1. Scroll to the top of this GitHub page.
2. Click the green **`Code`** button on the right.
3. Click **`Download ZIP`**.
4. Extract the downloaded folder to a location on your computer (e.g., your Desktop or Documents folder).

### Step 2: Launch the App
1. Open the extracted folder.
2. Double-click the file named **`run.bat`** (Windows Batch File).
3. *That's it!* A black terminal window will open and automatically:
   - Create a local Python environment.
   - Install the required libraries.
   - Configure the SQLite database.
   - Open your web browser to **`http://127.0.0.1:8000`** where the app is running.
4. Keep the black terminal window open while using the website. You can close it when you are finished sending your emails.

---

##  Security & Best Practices
* **Gmail App Passwords**: Do not use your standard Google password. Go to your Google Account Settings, turn on **2-Factor Authentication**, and generate a 16-character **App Password** for this application.
* **Keep your Database Private**: The database file `ecell_outreach.db` is stored locally on your hard drive and contains your SMTP credentials. It is listed in `.gitignore`, meaning you will never accidentally push your password or leads to GitHub. Never share your local `.db` file with anyone else.
* **Gmail Send Quotas**: Free Gmail accounts are limited to **500 emails/day**; Workspace accounts are limited to **2,000 emails/day**. Spread out large outreach campaigns over multiple days to maintain high sender authority.
