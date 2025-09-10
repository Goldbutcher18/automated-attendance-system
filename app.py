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

    conn = get_conn()
    df = pd.read_sql("SELECT * FROM attendance", conn)
    conn.close()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Records", len(df))
    col2.metric("Unique Students", df['email'].nunique() if not df.empty else 0)
    col3.metric("Today’s Attendance", df[df['date'].str.contains(datetime.now().strftime("%Y-%m-%d"))].shape[0])

    st.markdown("</div>", unsafe_allow_html=True)

elif page == "📝 Mark Attendance":
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## 📝 Mark Attendance")

    name = st.text_input("Enter your full name")
    email = st.text_input("Enter your college email")
    role = st.selectbox("Role", ["Student", "Teacher"])
    status = st.selectbox("Attendance Status", ["Present", "Absent", "Late"])

    if st.button("✅ Submit Attendance"):
        if name and email:
            conn = get_conn()
            c = conn.cursor()
            c.execute("INSERT INTO attendance(name,email,role,date,status) VALUES (?,?,?,?,?)",
                      (name, email, role, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), status))
            conn.commit()
            conn.close()
            st.success("Attendance recorded successfully!")
        else:
            st.error("Please fill in all fields.")

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
