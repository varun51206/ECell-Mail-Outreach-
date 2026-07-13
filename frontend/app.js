// Global State
let apiToken = localStorage.getItem("outreach_token") || "";
let currentUser = null;
let activeTab = "dashboard";
let currentCampaign = "live_project";
let templatesData = {};
let currentSettings = {};
let gridRows = [];
let quill = null;

const API_BASE = "/api";

// Initialize Page
document.addEventListener("DOMContentLoaded", () => {
    initTime();
    if (apiToken) {
        verifySession();
    } else {
        showAuth();
    }
});

function initTime() {
    const timeBadge = document.getElementById("current-time-badge");
    const updateTime = () => {
        const now = new Date();
        const yyyy = now.getFullYear();
        const mm = String(now.getMonth() + 1).padStart(2, '0');
        const dd = String(now.getDate()).padStart(2, '0');
        const hh = String(now.getHours()).padStart(2, '0');
        const min = String(now.getMinutes()).padStart(2, '0');
        timeBadge.textContent = `${yyyy}-${mm}-${dd} ${hh}:${min}`;
    };
    updateTime();
    setInterval(updateTime, 60000);
}

// Session Validation
async function verifySession() {
    try {
        const res = await fetch(`${API_BASE}/me`, {
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (res.ok) {
            currentUser = await res.json();
            showApp();
        } else {
            handleLogout();
        }
    } catch (e) {
        console.error("Session verification failed: ", e);
        showAuth();
    }
}

function showAuth() {
    document.getElementById("auth-container").classList.remove("hidden");
    document.getElementById("app-container").classList.add("hidden");
}

function showApp() {
    document.getElementById("auth-container").classList.add("hidden");
    document.getElementById("app-container").classList.remove("hidden");
    document.getElementById("display-username").textContent = currentUser.username;
    
    // Default actions on login
    switchTab("dashboard");
    loadSettings();
    loadAttachments();
    startStatusPolling();
}

function handleLogout() {
    fetch(`${API_BASE}/logout`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${apiToken}` }
    }).finally(() => {
        apiToken = "";
        localStorage.removeItem("outreach_token");
        currentUser = null;
        showAuth();
    });
}

// Auth Tab Switching
function switchAuthTab(type) {
    const loginTab = document.getElementById("tab-btn-login");
    const regTab = document.getElementById("tab-btn-register");
    const submitBtn = document.getElementById("auth-submit-btn");
    
    // Clear alerts
    document.getElementById("auth-error").classList.add("hidden");
    document.getElementById("auth-success").classList.add("hidden");

    if (type === "login") {
        loginTab.classList.add("active");
        regTab.classList.remove("active");
        submitBtn.textContent = "Sign In";
    } else {
        regTab.classList.add("active");
        loginTab.classList.remove("active");
        submitBtn.textContent = "Register Account";
    }
}

// Auth Submissions
async function handleAuth(event) {
    event.preventDefault();
    const usernameInput = document.getElementById("auth-username").value.trim();
    const passwordInput = document.getElementById("auth-password").value;
    const isLogin = document.getElementById("tab-btn-login").classList.contains("active");

    const errBox = document.getElementById("auth-error");
    const successBox = document.getElementById("auth-success");
    errBox.classList.add("hidden");
    successBox.classList.add("hidden");

    const payload = { username: usernameInput, password: passwordInput };
    const endpoint = isLogin ? "login" : "register";

    try {
        const res = await fetch(`${API_BASE}/${endpoint}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        
        if (!res.ok) {
            errBox.textContent = data.detail || "Authentication request failed.";
            errBox.classList.remove("hidden");
            return;
        }

        if (isLogin) {
            apiToken = data.token;
            localStorage.setItem("outreach_token", data.token);
            currentUser = { id: null, username: data.username }; // verifying session loads id
            await verifySession();
        } else {
            successBox.textContent = "Account registered successfully! You can now log in.";
            successBox.classList.remove("hidden");
            switchAuthTab("login");
        }
    } catch (e) {
        errBox.textContent = "Network error connecting to Outreach OS backend.";
        errBox.classList.remove("hidden");
    }
}

// Sidebar Navigation Router
function switchTab(tabId) {
    activeTab = tabId;
    
    // Switch menu states
    document.querySelectorAll(".menu-item").forEach(item => {
        item.classList.remove("active");
    });
    const activeMenuItem = document.getElementById(`menu-${tabId}`);
    if (activeMenuItem) activeMenuItem.classList.add("active");

    // Toggle panels
    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.add("hidden");
    });
    document.getElementById(`tab-content-${tabId}`).classList.remove("hidden");

    // Update Header Title
    const titles = {
        "dashboard": "System Dashboard",
        "leads": "Campaign Lead Manager",
        "templates": "Template Studio",
        "settings": "Settings & File Locker"
    };
    document.getElementById("tab-title").textContent = titles[tabId];

    // Trigger tab-specific loader
    if (tabId === "dashboard") loadDashboard();
    else if (tabId === "leads") loadLeadsTab();
    else if (tabId === "templates") loadTemplatesTab();
}


// --- DASHBOARD TAB ---
async function loadDashboard() {
    try {
        // Fetch stats
        const res = await fetch(`${API_BASE}/schedule/stats`, {
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (!res.ok) return;
        const stats = await res.json();
        
        // Sum total metrics
        let pending = 0, sent = 0, replied = 0, booked = 0, failed = 0;
        
        const tbody = document.getElementById("dashboard-campaigns-tbody");
        tbody.innerHTML = "";

        const campaigns = {
            "live_project": "Live Project Reachout",
            "pitch_deck": "Fundraising Pitch Decks",
            "all_purpose": "All-Purpose Mailer"
        };

        for (const [cId, name] of Object.entries(campaigns)) {
            const data = stats[cId] || { Pending: 0, Sent: 0, Replied: 0, "Call Booked": 0, Failed: 0, Closed: 0 };
            
            pending += data.Pending || 0;
            sent += data.Sent || 0;
            replied += data.Replied || 0;
            booked += data["Call Booked"] || 0;
            failed += data.Failed || 0;

            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>${name}</strong></td>
                <td><span class="status-pill pending">${data.Pending || 0}</span></td>
                <td><span class="status-pill sent">${data.Sent || 0}</span></td>
                <td><span class="status-pill replied">${data.Replied || 0}</span></td>
                <td><span class="status-pill booked">${data["Call Booked"] || 0}</span></td>
                <td><span class="status-pill failed">${data.Failed || 0}</span></td>
            `;
            tbody.appendChild(tr);
        }

        document.getElementById("stat-pending").textContent = pending;
        document.getElementById("stat-sent").textContent = sent;
        document.getElementById("stat-replied").textContent = replied;
        document.getElementById("stat-booked").textContent = booked;
        
        // Update general status
        await loadSettings();
        const dot = document.getElementById("smtp-status-dot");
        const text = document.getElementById("smtp-status-text");
        if (currentSettings.gmail_user && currentSettings.gmail_app_password) {
            dot.className = "status-dot active";
            text.textContent = `SMTP Configured (${currentSettings.gmail_user})`;
        } else {
            dot.className = "status-dot inactive";
            text.textContent = "SMTP Credentials Missing - Email worker is blocked";
        }
    } catch (e) {
        console.error("Error loading dashboard metrics: ", e);
    }
}


// --- LEAD MANAGER TAB ---
function loadLeadsTab() {
    currentCampaign = document.getElementById("lead-campaign-select").value;
    
    // Set default start date to today if empty
    const dateInput = document.getElementById("lead-start-date");
    if (!dateInput.value) {
        const today = new Date();
        const yyyy = today.getFullYear();
        const mm = String(today.getMonth() + 1).padStart(2, '0');
        const dd = String(today.getDate()).padStart(2, '0');
        dateInput.value = `${yyyy}-${mm}-${dd}`;
    }

    loadLeadsGrid();
    refreshScheduleQueue();
}

function getCampaignColumns(campaignId) {
    if (campaignId === "live_project") {
        return [
            { key: "email", label: "Email Recipient", placeholder: "founder@company.com" },
            { key: "first_name", label: "First Name", placeholder: "Amit" },
            { key: "company", label: "Company", placeholder: "Rapido" },
            { key: "role", label: "Role", placeholder: "Founder" },
            { key: "custom_field_1", label: "Problem Area", placeholder: "UX Research / Market Size" },
            { key: "custom_field_2", label: "Segment", placeholder: "Founder or POC" },
            { key: "start_from", label: "Start From Stage", placeholder: "initial", options: ["initial", "f1", "f2", "f3", "f4"] }
        ];
    } else if (campaignId === "pitch_deck") {
        return [
            { key: "email", label: "Founder Email", placeholder: "ceo@startup.io" },
            { key: "first_name", label: "First Name", placeholder: "Neha" },
            { key: "company", label: "Company", placeholder: "Zomato" },
            { key: "role", label: "Role", placeholder: "Founder & CEO" },
            { key: "start_from", label: "Start From Stage", placeholder: "initial", options: ["initial", "f1", "f2"] }
        ];
    } else { // all_purpose
        return [
            { key: "email", label: "Email Address", placeholder: "hr@company.com" },
            { key: "first_name", label: "First Name", placeholder: "Rahul" },
            { key: "company", label: "Target Entity", placeholder: "Google India" },
            { key: "custom_field_1", label: "Custom Variable 1", placeholder: "Resume.pdf" },
            { key: "custom_field_2", label: "Custom Variable 2", placeholder: "GTE Role" },
            { key: "start_from", label: "Start From Stage", placeholder: "initial", options: ["initial", "f1", "f2", "f3", "f4"] }
        ];
    }
}

function loadLeadsGrid() {
    currentCampaign = document.getElementById("lead-campaign-select").value;
    const cols = getCampaignColumns(currentCampaign);
    
    // Render Header
    const headerRow = document.getElementById("spreadsheet-header");
    headerRow.innerHTML = "<th>#</th>";
    cols.forEach(col => {
        const th = document.createElement("th");
        th.textContent = col.label;
        headerRow.appendChild(th);
    });
    headerRow.innerHTML += "<th style='width: 60px;'>Actions</th>";

    // Setup initial empty grid rows (e.g., 5 rows)
    gridRows = [];
    for (let i = 0; i < 5; i++) {
        gridRows.push(createEmptyLeadObject(cols));
    }
    renderGridRows();
}

function createEmptyLeadObject(cols) {
    const obj = {};
    cols.forEach(col => {
        obj[col.key] = "";
    });
    return obj;
}

function renderGridRows() {
    const tbody = document.getElementById("spreadsheet-tbody");
    tbody.innerHTML = "";
    const cols = getCampaignColumns(currentCampaign);

    gridRows.forEach((row, index) => {
        const tr = document.createElement("tr");
        
        // Index cell
        const indexTd = document.createElement("td");
        indexTd.textContent = index + 1;
        indexTd.className = "text-center";
        indexTd.style.fontWeight = "bold";
        indexTd.style.color = "var(--text-muted)";
        tr.appendChild(indexTd);

        // Value cells
        cols.forEach(col => {
            const td = document.createElement("td");
            if (col.options) {
                const select = document.createElement("select");
                select.style.border = "none";
                select.style.background = "transparent";
                select.style.color = "white";
                select.style.width = "100%";
                select.style.height = "100%";
                select.style.padding = "10px";
                
                col.options.forEach(opt => {
                    const option = document.createElement("option");
                    option.value = opt;
                    option.textContent = opt;
                    option.style.background = "#0f172a";
                    if (row[col.key] === opt || (!row[col.key] && opt === "initial")) {
                        option.selected = true;
                        row[col.key] = opt; // Save default state
                    }
                    select.appendChild(option);
                });
                
                select.onchange = (e) => {
                    gridRows[index][col.key] = e.target.value;
                };
                td.appendChild(select);
            } else {
                const input = document.createElement("input");
                input.type = col.key === "email" ? "email" : "text";
                input.placeholder = col.placeholder;
                input.value = row[col.key] || "";
                input.oninput = (e) => {
                    gridRows[index][col.key] = e.target.value;
                };
                td.appendChild(input);
            }
            tr.appendChild(td);
        });

        // Actions cell
        const actionTd = document.createElement("td");
        actionTd.className = "text-center";
        actionTd.innerHTML = `<button class="logout-btn" onclick="deleteGridRow(${index})" title="Delete row">❌</button>`;
        tr.appendChild(actionTd);

        tbody.appendChild(tr);
    });
}

function addGridRow() {
    const cols = getCampaignColumns(currentCampaign);
    gridRows.push(createEmptyLeadObject(cols));
    renderGridRows();
}

function deleteGridRow(index) {
    gridRows.splice(index, 1);
    if (gridRows.length === 0) {
        addGridRow();
    } else {
        renderGridRows();
    }
}

function clearGrid() {
    const cols = getCampaignColumns(currentCampaign);
    gridRows = [createEmptyLeadObject(cols)];
    renderGridRows();
}

async function bulkSaveLeads() {
    const startDate = document.getElementById("lead-start-date").value;
    if (!startDate) {
        alert("Please select a Campaign Start Date first.");
        return;
    }

    const validLeads = gridRows.filter(row => row.email && row.email.trim() !== "");
    if (validLeads.length === 0) {
        alert("Enter at least one lead with a valid email address.");
        return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    let errors = [];
    let warnings = [];
    
    validLeads.forEach((lead, idx) => {
        const rowNum = idx + 1;
        if (!emailRegex.test(lead.email.trim())) {
            errors.push(`Row ${rowNum}: '${lead.email}' is not a valid email address.`);
        }
        if (!lead.first_name || lead.first_name.trim() === "") {
            warnings.push(`Row ${rowNum}: First Name is missing.`);
        }
        if (!lead.company || lead.company.trim() === "") {
            warnings.push(`Row ${rowNum}: Company/Target Entity is missing.`);
        }
    });

    if (errors.length > 0) {
        alert("Please fix the following validation errors before saving:\n\n" + errors.join("\n"));
        return;
    }

    if (warnings.length > 0) {
        const proceed = confirm("Warnings found in your leads list:\n\n" + warnings.join("\n") + "\n\nDo you still want to save and generate schedules?");
        if (!proceed) return;
    }

    // Prepare payload
    const payload = {
        campaign_id: currentCampaign,
        leads: validLeads,
        start_date: startDate,
        offsets: {}, // Server will fallback to default offsets stored in user templates
        replace_mode: false // Appends to the current queue (use red 'Delete All Database Schedules' button to overwrite)
    };

    try {
        const res = await fetch(`${API_BASE}/schedule/bulk`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            clearGrid();
            refreshScheduleQueue();
        } else {
            alert(`Error scheduling: ${data.detail}`);
        }
    } catch (e) {
        alert("Connection error occurred while saving leads.");
    }
}

async function refreshScheduleQueue() {
    try {
        const res = await fetch(`${API_BASE}/schedule?campaign_id=${currentCampaign}`, {
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (!res.ok) return;
        const queue = await res.json();
        
        const tbody = document.getElementById("leads-queue-tbody");
        tbody.innerHTML = "";

        if (queue.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center">No active schedule found for this campaign. Add leads above to generate it.</td></tr>`;
            return;
        }

        queue.forEach(row => {
            const tr = document.createElement("tr");
            
            // Format status class
            const stClass = row.status.toLowerCase().replace(" ", "-");
            
            // Actions column - stops sending if Replied, Closed, etc.
            let actionsHtml = "";
            if (row.status === "Pending" || row.status === "Sent" || row.status === "Failed") {
                actionsHtml = `
                    <select onchange="updateLeadStatus('${row.email}', this.value)" style="padding: 4px; font-size: 0.75rem; width: auto;">
                        <option value="" disabled selected>Mark...</option>
                        <option value="Replied">Replied</option>
                        <option value="Call Booked">Call Booked</option>
                        <option value="Closed">Closed</option>
                        <option value="Pending">Reset Pending</option>
                    </select>
                `;
            } else {
                actionsHtml = `<button class="btn btn-secondary btn-sm" onclick="updateLeadStatus('${row.email}', 'Pending')" style="font-size: 0.7rem; padding: 2px 6px;">Unlock</button>`;
            }

            tr.innerHTML = `
                <td><strong>${row.first_name || ""}</strong> (${row.email})</td>
                <td>${row.company || "—"}</td>
                <td><code>${row.stage_step}</code></td>
                <td>${row.scheduled_date}</td>
                <td><span class="status-pill ${stClass}">${row.status}</span></td>
                <td><small>${row.notes || "No actions logged."}</small></td>
                <td>${actionsHtml}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error("Failed to load queue: ", e);
    }
}

async function updateLeadStatus(email, newStatus) {
    try {
        const res = await fetch(`${API_BASE}/schedule/update-status`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify({
                email: email,
                campaign_id: currentCampaign,
                status: newStatus,
                notes: `Manually marked as ${newStatus} by user`
            })
        });
        if (res.ok) {
            refreshScheduleQueue();
        } else {
            const data = await res.json();
            alert(`Error: ${data.detail}`);
        }
    } catch (e) {
        console.error("Failed to update status: ", e);
    }
}

async function clearRemoteSchedule() {
    if (!confirm("WARNING: This will permanently delete ALL schedules for this campaign in the database. Are you sure?")) {
        return;
    }
    try {
        const res = await fetch(`${API_BASE}/schedule/clear?campaign_id=${currentCampaign}`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (res.ok) {
            refreshScheduleQueue();
            alert("Database queue cleared.");
        }
    } catch (e) {
        alert("Failed to clear schedules.");
    }
}


// --- TEMPLATE STUDIO TAB ---
async function loadTemplatesTab() {
    const campaignId = document.getElementById("template-campaign-select").value;
    const stepSelect = document.getElementById("template-step-select");
    
    stepSelect.innerHTML = "";
    if (campaignId === "live_project") {
        addOption(stepSelect, "initial_founder", "Initial Step (Founder)");
        addOption(stepSelect, "initial_poc", "Initial Step (POC)");
        addOption(stepSelect, "f1", "Follow-up 1 (f1)");
        addOption(stepSelect, "f2", "Follow-up 2 (f2)");
        addOption(stepSelect, "f3", "Follow-up 3 (f3)");
        addOption(stepSelect, "f4", "Follow-up 4 (f4)");
    } else if (campaignId === "pitch_deck") {
        addOption(stepSelect, "initial", "Initial Step");
        addOption(stepSelect, "f1", "Follow-up 1 (f1)");
        addOption(stepSelect, "f2", "Follow-up 2 (f2)");
    } else { // all_purpose
        addOption(stepSelect, "initial", "Initial Step");
        addOption(stepSelect, "f1", "Follow-up 1 (f1)");
        addOption(stepSelect, "f2", "Follow-up 2 (f2)");
        addOption(stepSelect, "f3", "Follow-up 3 (f3)");
        addOption(stepSelect, "f4", "Follow-up 4 (f4)");
    }

    await fetchAllTemplates();
    loadTemplateView();
}

function formatDoc(cmd) {
    if (cmd === 'createLink') {
        const url = prompt("Enter URL (e.g. https://calendly.com/your-link):");
        if (url) {
            document.execCommand(cmd, false, url);
        }
    } else {
        document.execCommand(cmd, false, null);
    }
    updateTemplatePreview();
}

function addOption(select, value, label) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    select.appendChild(opt);
}

async function fetchAllTemplates() {
    try {
        const res = await fetch(`${API_BASE}/templates`, {
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (res.ok) {
            templatesData = await res.json();
        }
    } catch (e) {
        console.error("Error fetching templates: ", e);
    }
}

function loadTemplateView() {
    const campaignId = document.getElementById("template-campaign-select").value;
    const stepKey = document.getElementById("template-step-select").value;
    
    const subjectInput = document.getElementById("template-subject");
    const offsetInput = document.getElementById("template-offset");
    const editor = document.getElementById("template-body-editor");

    const cData = templatesData[campaignId] || {};
    const sData = cData[stepKey] || { subject: "", body: "", day_offset: 0 };

    subjectInput.value = sData.subject;
    offsetInput.value = sData.day_offset;
    
    if (editor) {
        let bodyHtml = sData.body || "";
        const isHtml = bodyHtml.trim().startsWith("<") || bodyHtml.includes("</div>") || bodyHtml.includes("</p>") || bodyHtml.includes("<br");
        if (!isHtml) {
            bodyHtml = bodyHtml.replace(/\n/g, "<br>");
        }
        editor.innerHTML = bodyHtml;
        editor.oninput = updateTemplatePreview;
    }

    subjectInput.oninput = updateTemplatePreview;
    updateTemplatePreview();
}

function updateTemplatePreview() {
    const subjVal = document.getElementById("template-subject").value;
    const editor = document.getElementById("template-body-editor");
    const bodyVal = editor ? editor.innerHTML : "";
    
    const sample = {
        FirstName: "Rohan",
        Company: "Acme Corp",
        Role: "Founder",
        Custom1: "Consumer GTM & Branding",
        Custom2: "Resume_Portfolio.pdf",
        SenderName: currentSettings.sender_name || "Your Name",
        SenderPhone: currentSettings.sender_phone || "+91 XXXXX XXXXX"
    };

    let subject = subjVal;
    let body = bodyVal;

    for (const [k, v] of Object.entries(sample)) {
        const rg = new RegExp(`{{${k}}}`, 'g');
        subject = subject.replace(rg, v);
        body = body.replace(rg, v);
    }

    document.getElementById("preview-subject-text").textContent = subject;
    document.getElementById("preview-body-text").innerHTML = body;
}

async function saveTemplate() {
    const campaignId = document.getElementById("template-campaign-select").value;
    const stepKey = document.getElementById("template-step-select").value;
    const subject = document.getElementById("template-subject").value;
    const editor = document.getElementById("template-body-editor");
    const body = editor ? editor.innerHTML : "";
    const offset = parseInt(document.getElementById("template-offset").value) || 0;

    const payload = {
        campaign_id: campaignId,
        step_key: stepKey,
        subject: subject,
        body: body,
        day_offset: offset
    };

    try {
        const res = await fetch(`${API_BASE}/templates/save`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert("Template saved successfully.");
            await fetchAllTemplates();
        } else {
            const err = await res.json();
            alert(`Error: ${err.detail}`);
        }
    } catch (e) {
        alert("Failed to save template.");
    }
}


// --- SETTINGS & ATTACHMENTS TAB ---
async function loadSettings() {
    try {
        const res = await fetch(`${API_BASE}/settings`, {
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (!res.ok) return;
        currentSettings = await res.json();
        
        // Fill form fields
        document.getElementById("settings-sender-name").value = currentSettings.sender_name;
        document.getElementById("settings-sender-phone").value = currentSettings.sender_phone;
        document.getElementById("settings-gmail-user").value = currentSettings.gmail_user;
        document.getElementById("settings-gmail-password").value = currentSettings.gmail_app_password;
        document.getElementById("settings-public-url").value = currentSettings.public_url || "http://127.0.0.1:8000";

        // Render stop banner / button state
        const stopBanner = document.getElementById("stop-banner");
        const stopBtn = document.getElementById("emergency-btn");
        if (currentSettings.emergency_stop) {
            stopBanner.classList.remove("hidden");
            stopBtn.className = "btn btn-success btn-block";
            stopBtn.textContent = "🔓 CLEAR EMERGENCY STOP";
        } else {
            stopBanner.classList.add("hidden");
            stopBtn.className = "btn btn-danger btn-block";
            stopBtn.textContent = "🚨 ACTIVATE EMERGENCY STOP";
        }
    } catch (e) {
        console.error("Failed to load settings: ", e);
    }
}

async function saveSettings(event) {
    event.preventDefault();
    const payload = {
        sender_name: document.getElementById("settings-sender-name").value,
        sender_phone: document.getElementById("settings-sender-phone").value,
        gmail_user: document.getElementById("settings-gmail-user").value,
        gmail_app_password: document.getElementById("settings-gmail-password").value,
        public_url: document.getElementById("settings-public-url").value
    };

    try {
        const res = await fetch(`${API_BASE}/settings`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert("Settings updated.");
            loadSettings();
        } else {
            const data = await res.json();
            alert(`Error updating settings: ${data.detail}`);
        }
    } catch (e) {
        alert("Failed to save settings.");
    }
}

async function toggleEmergencyStop() {
    try {
        const res = await fetch(`${API_BASE}/settings/toggle-stop`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (res.ok) {
            const data = await res.json();
            alert(`Emergency Stop is now ${data.emergency_stop ? "ACTIVE" : "CLEARED"}.`);
            loadSettings();
        }
    } catch (e) {
        alert("Failed to toggle emergency stop.");
    }
}

async function runSmtpTest() {
    const email = document.getElementById("test-smtp-email").value.trim();
    if (!email) {
        alert("Enter a target email to send the test message to.");
        return;
    }

    const resultBox = document.getElementById("smtp-test-result");
    resultBox.textContent = "Sending test email, please wait...";
    resultBox.className = "alert alert-info";
    resultBox.classList.remove("hidden");

    try {
        const res = await fetch(`${API_BASE}/settings/test-smtp`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify({ recipient_email: email })
        });
        const data = await res.json();
        if (res.ok) {
            resultBox.textContent = "SMTP connection verified! Check your inbox.";
            resultBox.className = "alert alert-success";
        } else {
            resultBox.textContent = `SMTP Error: ${data.detail}`;
            resultBox.className = "alert alert-danger";
        }
    } catch (e) {
        resultBox.textContent = "Failed to communicate with SMTP validator.";
        resultBox.className = "alert alert-danger";
    }
}

// File Attachment Locker
async function loadAttachments() {
    try {
        const res = await fetch(`${API_BASE}/attachments`, {
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (!res.ok) return;
        const list = await res.json();
        
        const ul = document.getElementById("uploaded-files-list");
        ul.innerHTML = "";

        if (list.length === 0) {
            ul.innerHTML = "<li>No files uploaded yet.</li>";
            return;
        }

        const mapNames = {
            "live_project": "Live Project (LP Report)",
            "pitch_deck": "Fundraising (Pitch Deck)",
            "all_purpose": "All-Purpose (Resume/Portfolio)"
        };

        list.forEach(file => {
            const li = document.createElement("li");
            li.innerHTML = `
                <div class="file-info">
                    <strong>${file.file_name}</strong>
                    <span>Category: ${mapNames[file.campaign_id] || file.campaign_id} • Uploaded ${new Date(file.uploaded_at).toLocaleDateString()}</span>
                </div>
                <div class="file-actions">
                    <button onclick="deleteAttachment('${file.campaign_id}')" title="Delete attachment">🗑️</button>
                </div>
            `;
            ul.appendChild(li);
        });
    } catch (e) {
        console.error("Failed to load attachments: ", e);
    }
}

async function handleFileSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const campaignId = document.getElementById("attachment-campaign-select").value;
    const statusBox = document.getElementById("upload-status");
    
    statusBox.textContent = "Uploading file, please wait...";
    statusBox.className = "alert alert-info";
    statusBox.classList.remove("hidden");

    const formData = new FormData();
    formData.append("campaign_id", campaignId);
    formData.append("file", file);

    try {
        const res = await fetch(`${API_BASE}/attachments/upload`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${apiToken}` },
            body: formData
        });
        const data = await res.json();
        if (res.ok) {
            statusBox.textContent = `Successfully uploaded: ${data.filename}`;
            statusBox.className = "alert alert-success";
            loadAttachments();
        } else {
            statusBox.textContent = `Upload failed: ${data.detail}`;
            statusBox.className = "alert alert-danger";
        }
    } catch (e) {
        statusBox.textContent = "Network error during upload.";
        statusBox.className = "alert alert-danger";
    }
    
    // Clear input
    event.target.value = "";
    setTimeout(() => { statusBox.classList.add("hidden"); }, 5000);
}

async function deleteAttachment(campaignId) {
    if (!confirm("Are you sure you want to delete this attachment?")) return;
    try {
        const res = await fetch(`${API_BASE}/attachments/${campaignId}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (res.ok) {
            loadAttachments();
        }
    } catch (e) {
        console.error("Failed to delete attachment: ", e);
    }
}


// --- MANUAL SENDING CONTROLS ---
let sendingStatusInterval = null;

async function triggerManualSend() {
    try {
        const res = await fetch(`${API_BASE}/schedule/send`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        
        if (res.ok) {
            startStatusPolling();
        } else {
            const data = await res.json();
            alert(data.detail || "Failed to trigger email send.");
        }
    } catch (e) {
        console.error("Error triggering sending: ", e);
        alert("Failed to connect to outreach engine.");
    }
}

function startStatusPolling() {
    if (sendingStatusInterval) clearInterval(sendingStatusInterval);
    
    pollSendingStatus();
    sendingStatusInterval = setInterval(pollSendingStatus, 1000);
}

async function pollSendingStatus() {
    if (!apiToken) {
        if (sendingStatusInterval) clearInterval(sendingStatusInterval);
        return;
    }
    
    try {
        const res = await fetch(`${API_BASE}/schedule/send-status`, {
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        if (!res.ok) return;
        const state = await res.json();
        
        updateSendingUI(state);
        
        if (!state.is_sending) {
            if (sendingStatusInterval) {
                clearInterval(sendingStatusInterval);
                sendingStatusInterval = null;
                if (activeTab === "dashboard") loadDashboard();
                if (activeTab === "leads") refreshScheduleQueue();
            }
        }
    } catch (e) {
        console.error("Error polling sending status: ", e);
    }
}

function updateSendingUI(state) {
    const dashBtn = document.getElementById("dashboard-send-btn");
    const queueBtn = document.getElementById("queue-send-btn");
    const dashStatus = document.getElementById("dashboard-send-status");
    const queueStatus = document.getElementById("queue-send-status");
    const dot = document.getElementById("engine-status-dot");
    const text = document.getElementById("engine-status-text");

    if (state.is_sending) {
        if (dashBtn) {
            dashBtn.disabled = true;
            dashBtn.textContent = "⏳ Sending Emails...";
        }
        if (queueBtn) {
            queueBtn.disabled = true;
            queueBtn.textContent = "⏳ Sending...";
        }
        
        const logContent = `<strong>Outreach Progress:</strong> ${state.current_log}<br>` + 
                           `<small>Mails processed: ${state.sent_count} / ${state.total_to_send}</small>`;
        
        if (dashStatus) {
            dashStatus.innerHTML = logContent;
            dashStatus.className = "alert alert-info";
            dashStatus.classList.remove("hidden");
        }
        if (queueStatus) {
            queueStatus.innerHTML = logContent;
            queueStatus.className = "alert alert-info";
            queueStatus.classList.remove("hidden");
        }
        
        if (dot) dot.className = "status-dot active";
        if (text) text.textContent = "Sending Batch...";
    } else {
        if (dashBtn) {
            dashBtn.disabled = false;
            dashBtn.textContent = "🚀 Start Campaign Send";
        }
        if (queueBtn) {
            queueBtn.disabled = false;
            queueBtn.textContent = "🚀 Start Sending Due Mails";
        }
        
        if (state.current_log && state.current_log.includes("complete")) {
            const summary = `<strong>Success:</strong> ${state.current_log}`;
            if (dashStatus) {
                dashStatus.innerHTML = summary;
                dashStatus.className = "alert alert-success";
                dashStatus.classList.remove("hidden");
                setTimeout(() => dashStatus.classList.add("hidden"), 8000);
            }
            if (queueStatus) {
                queueStatus.innerHTML = summary;
                queueStatus.className = "alert alert-success";
                queueStatus.classList.remove("hidden");
                setTimeout(() => queueStatus.classList.add("hidden"), 8000);
            }
        } else {
            if (dashStatus) dashStatus.classList.add("hidden");
            if (queueStatus) queueStatus.classList.add("hidden");
        }
        
        if (dot) dot.className = "status-dot active";
        if (text) text.textContent = "Manual Send Trigger";
    }
}

function filterQueueTable() {
    const query = document.getElementById("queue-search-input").value.trim().toLowerCase();
    const tbody = document.getElementById("leads-queue-tbody");
    const trs = tbody.getElementsByTagName("tr");
    
    for (let i = 0; i < trs.length; i++) {
        const tr = trs[i];
        if (tr.cells.length <= 1) continue; // Skip single info rows
        
        const text = tr.innerText.toLowerCase();
        if (text.includes(query)) {
            tr.style.display = "";
        } else {
            tr.style.display = "none";
        }
    }
}

async function sendTestEmail() {
    const campaignId = document.getElementById("template-campaign-select").value;
    const stepKey = document.getElementById("template-step-select").value;
    const subject = document.getElementById("template-subject").value;
    const editor = document.getElementById("template-body-editor");
    const body = editor ? editor.innerHTML : "";
    const btn = document.getElementById("send-test-btn");

    if (!subject.trim() || !body.trim()) {
        alert("Please enter a subject and body for the template first.");
        return;
    }

    btn.disabled = true;
    btn.textContent = "⌛ Sending Test...";

    try {
        const res = await fetch(`${API_BASE}/templates/send-test`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${apiToken}`
            },
            body: JSON.stringify({ campaign_id: campaignId, step_key: stepKey, subject, body })
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
        } else {
            alert(`Error sending test email: ${data.detail}`);
        }
    } catch (e) {
        alert("Network error sending test email. Check server status.");
    } finally {
        btn.disabled = false;
        btn.textContent = "✉️ Send Test Email to Self";
    }
}

async function syncGmailReplies() {
    const btn = document.getElementById("sync-replies-btn");
    if (!btn) return;
    
    btn.disabled = true;
    btn.textContent = "⌛ Syncing Inbox...";

    try {
        const res = await fetch(`${API_BASE}/schedule/sync-replies`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${apiToken}` }
        });
        const data = await res.json();
        if (res.ok) {
            alert(data.message);
            refreshScheduleQueue();
        } else {
            alert(`Sync failed: ${data.detail}`);
        }
    } catch (e) {
        alert("Failed to communicate with the reply sync server.");
    } finally {
        btn.disabled = false;
        btn.textContent = "📥 Sync Replies via Gmail";
    }
}
