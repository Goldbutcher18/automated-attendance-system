import os
import io
import time
import base64
import math
import sqlite3
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from PIL import Image

import streamlit as st
import qrcode
import bcrypt

# Mock email sending (for demo)
def send_email(to_email, subject, body):
    print(f"--- EMAIL TO: {to_email} ---\n{subject}\n{body}\n-------------------------")

# Mock NFC reader
# In real system, this would read from a USB/NFC device. Here we simulate with manual card input.
def read_nfc_card():
    return st.text_input("Tap your NFC/RFID card (enter card ID manually for demo)")

try:
    import cv2
    OPENCV_OK = True
except Exception:
    OPENCV_OK = False

DB_PATH = "attendance.db"
SESSION_TTL_MIN = 20

# =============================
# DB + Helpers (same as before)
# =============================
# (For brevity, keeping same DB schema as earlier)

# ... [KEEP ALL EXISTING FUNCTIONS UNCHANGED from earlier version: get_conn, init_db, create_user, authenticate, etc.] ...

# =============================
# UI with Branding
# =============================

def main():
    st.set_page_config(page_title="Smart Attendance – BV(DU)", page_icon="🪪", layout="wide")
    st.markdown("""
    <h1 style='text-align: center; color: #E85A0C;'>🪪 Bharti Vidyapeeth (Deemed to be University)</h1>
    <h3 style='text-align: center; color: #003366;'>Smart Automated Attendance System</h3>
    """, unsafe_allow_html=True)

    init_db()
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        # Login & Signup tabs remain unchanged
        # ...
        st.stop()

    user = st.session_state.user

    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/en/f/f4/Bharati_Vidyapeeth_Deemed_University_logo.png", width=140)
        st.write(f"Welcome, **{user['name']}** ({user['role']})")
        if st.button("Sign out"):
            st.session_state.user = None
            st.experimental_rerun()

    role = user["role"]
    if role == "admin":
        admin_view(user)
    elif role == "teacher":
        teacher_view(user)
    else:
        student_view(user)

# =============================
# Student View (add NFC option)
# =============================

def student_view(user):
    st.subheader("Student Portal")
    tab_scan, tab_code, tab_nfc, tab_profile, tab_history = st.tabs(["Scan QR", "Enter code", "NFC/RFID", "Profile", "History"])

    # [QR + Code views unchanged]

    with tab_nfc:
        st.caption("Tap your NFC/RFID card (demo: type card ID)")
        card_id = read_nfc_card()
        sid = st.number_input("Session ID", min_value=1, step=1, key="nfc_sid")
        if st.button("Mark via NFC"):
            if not card_id:
                st.error("Card ID required")
            else:
                s = get_session(int(sid))
                if not s:
                    st.error("Session not found")
                else:
                    ok, msg = mark_attendance(int(sid), user["id"], method="nfc")
                    if ok:
                        st.success(f"Attendance marked: {msg}")
                    else:
                        st.error(msg)

    # [Profile + History unchanged]

# =============================
# Teacher View (send absentee emails)
# =============================

def teacher_view(user):
    st.subheader("Teacher Dashboard")
    # [Course selection and session start unchanged]

    # Add absentee notification button under session details
    rows = list_sessions(1, since_days=7)  # example: recent week
    for s in rows:
        with st.expander(f"Session #{s['id']} • {s['start_ts']} → {s['end_ts']}"):
            conn = get_conn()
            df = pd.read_sql_query(
                "SELECT u.id, u.name, u.email FROM enrollments e JOIN users u ON u.id=e.user_id WHERE e.course_id=?",
                conn, params=(s["course_id"],))
            marked = pd.read_sql_query(
                "SELECT user_id FROM attendance WHERE session_id=?", conn, params=(s["id"],))
            conn.close()
            absentees = df[~df["id"].isin(marked["user_id"])]
            if st.button(f"Send email alerts for Session {s['id']}"):
                for _, row in absentees.iterrows():
                    send_email(row["email"], "Attendance Alert", f"Dear {row['name']}, you missed session {s['id']}.")
                st.success(f"Emails sent to {len(absentees)} absentees.")
               """
Streamlit UI/UX Template for "Smart Attendance" (Bharti Vidyapeeth)
- Clean layout, colors, accessible typography
- Sidebar navigation, cards, metrics, tables, QR preview
- Lightweight: SQLite + Pillow + qrcode optional (you can remove qrcode if not needed)
- Meant to be a UI/UX layer — wire your backend functions where noted.
"""

import streamlit as st
import sqlite3
from io import BytesIO
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import qrcode
import pandas as pd

# ---------- Page config & branding ----------
st.set_page_config(page_title="Smart Attendance – Bharti Vidyapeeth",
                   layout="wide",
                   page_icon="🎓")

# BRAND COLORS (Bharti Vidyapeeth inspired)
PRIMARY = "#E85A0C"   # orange
SECONDARY = "#003366" # deep blue
BG = "#F7F7F8"
CARD = "#FFFFFF"

# ---------- Inject small CSS for nicer visuals ----------
st.markdown(f"""
<style>
/* Page background */
.reportview-container .main {{
  background-color: {BG};
}}

/* Sidebar */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, {SECONDARY}, #1b4b72);
  color: white;
}}

/* Title */
h1 {{
  color: {SECONDARY};
}}

/* Cards */
.card {{
  background: {CARD};
  padding: 18px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}

/* Buttons */
.stButton>button {{
  border-radius: 8px;
}}

/* Small utility */
.small-muted {{ color: #666666; font-size:12px; }}
</style>
""", unsafe_allow_html=True)

# ---------- Simple DB helpers (demo data) ----------
DB = "ui_demo.db"

def get_conn():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_demo_db():
    conn = get_conn()
    cur = conn.cursor()
    # users table (very small demo)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        role TEXT
    );
    """)
    # attendance
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        status TEXT
    );
    """)
    # seed demo users if none
    cur.execute("SELECT COUNT(*) as n FROM users")
    if cur.fetchone()["n"] == 0:
        demo = [
            ("Amit Kumar","amit@bv.edu","student"),
            ("Priya Sharma","priya@bv.edu","student"),
            ("Dr. R. Rao","rao@bv.edu","teacher"),
        ]
        cur.executemany("INSERT INTO users(name,email,role) VALUES(?,?,?)", demo)
    conn.commit()
    conn.close()

# initialize demo DB
init_demo_db()

# ---------- Helper UI components ----------
def page_header(title, subtitle=None, help_text=None):
    col1, col2 = st.columns([0.8, 0.2])
    with col1:
        st.markdown(f"## {title}")
        if subtitle:
            st.markdown(f"<div class='small-muted'>{subtitle}</div>", unsafe_allow_html=True)
    with col2:
        if help_text:
            st.info(help_text)

def profile_card(name="User", role="student", email="user@example.com"):
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    cols = st.columns([1,3])
    with cols[0]:
        # simple avatar: colored circle with initials
        initials = "".join([p[0] for p in name.split()][:2]).upper()
        avatar = Image.new("RGB", (96,96), color=PRIMARY)
        draw = ImageDraw.Draw(avatar)
        draw.text((20,25), initials, fill="white")
        st.image(avatar, width=96)
    with cols[1]:
        st.markdown(f"### {name}")
        st.markdown(f"**{role.title()}** • {email}")
        st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
        st.button("Sign out")
    st.markdown("</div>", unsafe_allow_html=True)

def small_metric(label, value, delta=None):
    if delta is not None:
        st.metric(label, value, delta)
    else:
        st.metric(label, value)

def generate_qr_image(text: str, size=260):
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    # resize cleanly
    img = img.resize((size, size))
    return img

# ---------- Sidebar with navigation ----------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/f/f4/Bharati_Vidyapeeth_Deemed_University_logo.png", width=150)
st.sidebar.markdown("---")
st.sidebar.markdown("### Navigation")
page = st.sidebar.radio("", ["Dashboard", "Mark Attendance", "Sessions", "Reports", "Admin & Settings"])
st.sidebar.markdown("---")
st.sidebar.markdown("#### Quick actions")
st.sidebar.button("New Session")
st.sidebar.button("Export CSV")
st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ by Bharti Vidyapeeth")

# ---------- Main UI (pages) ----------
if page == "Dashboard":
    page_header("Dashboard", subtitle="Overview of today's attendance", help_text="Shows summary metrics and recent activity.")
    # top metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        small_metric("Total Students", "120")
    with col2:
        small_metric("Present Today", "102", delta="+6")
    with col3:
        small_metric("Absent Today", "18", delta="-6")
    with col4:
        small_metric("Ongoing Sessions", "1")

    st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)

    # recent attendance table (pull from demo DB)
    conn = get_conn()
    df = pd.read_sql_query("""
        SELECT a.id, u.name as student, a.date, a.status
        FROM attendance a LEFT JOIN users u ON u.id=a.user_id
        ORDER BY a.date DESC LIMIT 10
    """, conn)
    conn.close()

    st.markdown("### Recent attendance")
    if df.empty:
        st.info("No attendance recorded yet. Use 'Mark Attendance' or create a session.")
    else:
        st.dataframe(df)

    # annoucement card
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Announcements")
    st.write("- Demo Mode: This is a UI mockup. Connect your backend to save real data.")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Mark Attendance":
    page_header("Mark Attendance", subtitle="Quickly mark your attendance or scan a session QR.")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    cols = st.columns([2,1])
    with cols[0]:
        st.markdown("#### Student Quick Mark")
        email = st.text_input("Enter your college email")
        choice = st.selectbox("Status", ["Present", "Late", "Absent"])
        if st.button("Mark My Attendance"):
            # demo: find user and add attendance row
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT id FROM users WHERE email=?", (email.strip(),))
            row = cur.fetchone()
            if row:
                cur.execute("INSERT INTO attendance(user_id,date,status) VALUES(?,?,?)",
                            (row["id"], datetime.utcnow().strftime("%Y-%m-%d"), choice))
                conn.commit()
                st.success("Marked successfully ✅")
            else:
                st.error("Email not found — please register with admin.")
            conn.close()
    with cols[1]:
        st.markdown("#### QR Session (demo)")
        sample_payload = "AATT://SID=123;COURSE=CS101;CODE=ABC123"
        qr_img = generate_qr_image(sample_payload)
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        st.image(buf.getvalue(), width=200)
        st.caption("Show this QR on projector for students to scan.")

    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Sessions":
    page_header("Sessions", subtitle="Create or manage live attendance sessions.")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    with st.form("new_session"):
        st.markdown("### Create new session")
        course_code = st.text_input("Course Code", value="CS101")
        ttl = st.number_input("Session duration (minutes)", min_value=5, max_value=180, value=20)
        require_face = st.checkbox("Require face check (not implemented in demo)", value=False)
        geo = st.checkbox("Enable geofence (not implemented in demo)", value=False)
        if st.form_submit_button("Start session"):
            # In production: create session record and generate QR payload
            payload = f"AATT://SID={int(datetime.utcnow().timestamp())};COURSE={course_code};CODE={base36 := 'AB' + '1'}"
            st.success("Session started")
            st.image(generate_qr_image(payload), width=240)
            st.markdown(f"**Code:** `{payload.split('CODE=')[-1]}`")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Reports":
    page_header("Reports", subtitle="Download attendance reports and analytics.")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    # Simple filter and CSV export
    conn = get_conn()
    df_all = pd.read_sql_query("""
        SELECT a.id, u.name as student, u.email, a.date, a.status
        FROM attendance a LEFT JOIN users u ON u.id=a.user_id
        ORDER BY a.date DESC
    """, conn)
    conn.close()
    st.markdown("### Filters")
    cols = st.columns([3,1,1])
    with cols[0]:
        name_q = st.text_input("Student name contains")
    with cols[1]:
        date_from = st.date_input("From", value=datetime.utcnow().date() - timedelta(days=30))
    with cols[2]:
        date_to = st.date_input("To", value=datetime.utcnow().date())
    mask = (df_all['date'] >= date_from.strftime("%Y-%m-%d")) & (df_all['date'] <= date_to.strftime("%Y-%m-%d"))
    if name_q:
        mask &= df_all['student'].str.contains(name_q, case=False, na=False)
    df_filtered = df_all[mask]
    st.dataframe(df_filtered)
    csv = df_filtered.to_csv(index=False).encode()
    st.download_button("Download CSV", csv, file_name="attendance_report.csv")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Admin & Settings":
    page_header("Admin & Settings", subtitle="Manage users, courses, and app settings.")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Users")
    conn = get_conn()
    users = pd.read_sql_query("SELECT id,name,email,role FROM users ORDER BY name", conn)
    conn.close()
    st.dataframe(users)
    with st.expander("Add demo user"):
        nm = st.text_input("Name", key="adm_name")
        em = st.text_input("Email", key="adm_email")
        rr = st.selectbox("Role", ["student","teacher","admin"], key="adm_role")
        if st.button("Add user"):
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("INSERT INTO users(name,email,role) VALUES(?,?,?)", (nm,em,rr))
            conn.commit()
            conn.close()
            st.success("User added. Refresh the page to see the change.")
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- Footer ----------
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown(f"<div class='small-muted'>© {datetime.utcnow().year} Bharti Vidyapeeth (Deemed to be University) • Demo UI/UX</div>", unsafe_allow_html=True)
