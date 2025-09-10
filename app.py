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

import streamlit as st
import sqlite3
import pandas as pd
import qrcode
from io import BytesIO
from datetime import datetime
from PIL import Image

# ---------------- Page Setup ----------------
st.set_page_config(
    page_title="Smart Attendance | Bharti Vidyapeeth",
    layout="wide",
    page_icon="🎓"
)

# ---------------- Custom CSS ----------------
st.markdown("""
<style>
/* Background */
.main {
    background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%);
    font-family: 'Segoe UI', sans-serif;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f4c75, #3282b8);
    color: white;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: white;
}

/* Title */
h1, h2, h3 {
    font-weight: 700;
    color: #0f4c75;
}

/* Glassmorphism Cards */
.card {
    background: rgba(255, 255, 255, 0.65);
    border-radius: 16px;
    padding: 20px;
    margin: 10px 0;
    backdrop-filter: blur(12px) saturate(180%);
    -webkit-backdrop-filter: blur(12px) saturate(180%);
    border: 1px solid rgba(255, 255, 255, 0.3);
}

/* Buttons */
.stButton>button {
    background: linear-gradient(90deg, #3282b8, #0f4c75);
    color: white;
    border-radius: 8px;
    padding: 0.6rem 1.2rem;
    border: none;
    font-weight: bold;
}
.stButton>button:hover {
    background: linear-gradient(90deg, #0f4c75, #3282b8);
}

/* Footer */
.footer {
    text-align: center;
    padding: 15px;
    color: #666;
    font-size: 13px;
}
</style>
""", unsafe_allow_html=True)


# ---------------- Database ----------------
def get_conn():
    conn = sqlite3.connect("attendance_ui.db", check_same_thread=False)
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS attendance (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT,
                 email TEXT,
                 role TEXT,
                 date TEXT,
                 status TEXT)""")
    conn.commit()
    conn.close()

init_db()

# ---------------- QR Generator ----------------
def generate_qr(data: str):
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf

# ---------------- Sidebar ----------------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/en/f/f4/Bharati_Vidyapeeth_Deemed_University_logo.png", width=150)
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to", ["🏠 Dashboard", "📝 Mark Attendance", "📊 Reports", "⚙️ Admin"])
st.sidebar.markdown("---")
st.sidebar.info("Smart Attendance System\nBharti Vidyapeeth (Deemed to be University)")

# ---------------- Pages ----------------
if page == "🏠 Dashboard":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 🎓 Smart Attendance Dashboard")
    st.write("Welcome to the Smart Attendance System for **Bharti Vidyapeeth (Deemed to be University)**.")
    st.write("Track attendance, generate session QR codes, and monitor reports in real time.")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "📝 Mark Attendance":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 📝 Mark Attendance")

    name = st.text_input("Enter your full name")
    email = st.text_input("Enter your college email")
    role = st.selectbox("Role", ["Student", "Teacher"])
    status = st.selectbox("Attendance Status", ["Present", "Absent", "Late"])

    if st.button("✅ Submit Attendance"):
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO attendance(name,email,role,date,status) VALUES (?,?,?,?,?)",
                  (name, email, role, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status))
        conn.commit()
        conn.close()
        st.success("Attendance recorded successfully!")

    st.markdown("### 📷 QR Code for Session")
    session_data = f"{name}-{email}-{role}-{datetime.now()}"
    qr_img = generate_qr(session_data)
    st.image(qr_img, width=220)

    st.markdown("</div>", unsafe_allow_html=True)

elif page == "📊 Reports":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 📊 Attendance Reports")
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM attendance", conn)
    conn.close()

    if df.empty:
        st.info("No attendance data yet.")
    else:
        st.dataframe(df)
        csv = df.to_csv(index=False).encode()
        st.download_button("⬇️ Download Report as CSV", csv, "attendance_report.csv", "text/csv")

    st.markdown("</div>", unsafe_allow_html=True)

elif page == "⚙️ Admin":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## ⚙️ Admin Panel")
    st.write("Manage system settings and monitor database records.")

    conn = get_conn()
    df = pd.read_sql("SELECT * FROM attendance", conn)
    conn.close()
    st.metric("Total Records", len(df))
    st.metric("Unique Students", df['email'].nunique() if not df.empty else 0)

    st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Footer ----------------
st.markdown("<div class='footer'>© 2025 Bharti Vidyapeeth (Deemed to be University) | Smart Attendance System</div>", unsafe_allow_html=True)



