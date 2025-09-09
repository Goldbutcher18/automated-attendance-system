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





