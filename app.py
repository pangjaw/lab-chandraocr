import streamlit as st
import re
import os
import zipfile
import json
import hashlib
import pandas as pd
import platform
import pytesseract
from io import BytesIO
from PIL import Image
from pdf2image import convert_from_bytes
from google.cloud import firestore
from google.oauth2 import service_account

# --- 1. KONFIGURASI OCR (TESSERACT) ---
# Jika di laptop (Windows), tentukan path exe-nya. Jika di Cloud (Linux), otomatis terdeteksi.
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- 2. FUNGSI KEAMANAN & DATABASE ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# Koneksi Firestore
if "firebase" in st.secrets:
    key_dict = dict(st.secrets["firebase"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict['project_id'])
else:
    st.error("Konfigurasi Firebase tidak ditemukan di Secrets!")
    st.stop()

def get_user_db(email):
    doc = db.collection("users").document(email).get()
    if doc.exists:
        return doc.to_dict().get("mapping", {})
    return {"BOGOR": "BOO"}

def save_user_db(email, mapping):
    db.collection("users").document(email).set({"mapping": mapping})

# --- 3. LOGIKA LOGIN ---
if 'connected' not in st.session_state:
    st.session_state.connected = False

if not st.session_state.connected:
    st.title("🔐 Login Ceklis Sintelis")
    email_in = st.text_input("Email/Username").lower().strip()
    pass_in = st.text_input("Password", type="password")
    c1, c2 = st.columns(2)
    
    if c1.button("Login", use_container_width=True):
        u_cred = db.collection("credentials").document(email_in).get()
        if u_cred.exists and hash_password(pass_in) == u_cred.to_dict().get("password"):
            st.session_state.connected = True
            st.session_state.user_email = email_in
            st.session_state.user_name = email_in.split("@")[0].upper()
            st.rerun()
        else:
            st.error("Login Gagal!")
    if c2.button("Daftar Akun Baru", use_container_width=True):
        if email_in and pass_in:
            db.collection("credentials").document(email_in).set({"password": hash_password(pass_in)})
            st.success("Berhasil daftar! Silakan Login.")
    st.stop()

# --- 4. SESSION STATE & INFO USER ---
user_email = st.session_state.user_email
user_name = st.session_state.user_name

if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)
if 'temp_bulk' not in st.session_state:
    st.session_state.temp_bulk = []

# --- 5. SIDEBAR (NAVIGASI & DATABASE) ---
with st.sidebar:
    st.write(f"Halo, **{user_name}**")
    menu = st.radio("Pilih Menu:", ["📍 Kelola Lokasi", "📦 Backup & Restore"])
    st.divider()

    if menu == "📍 Kelola Lokasi":
        st.subheader("🚀 Bulk Input")
        st.caption("Format: LOKASI,SINGKATAN (Gunakan baris baru)")
        bulk_area = st.text_area("Paste data di sini:", height=150, placeholder="BOGOR,BOO\nDEPOK,DP")
        
        cb1, cb2 = st.columns(2)
        if cb1.button("🧐 Pratinjau", use_container_width=True):
            lines = bulk_area.strip().split('\n')
            st.session_state.temp_bulk = []
            for line in lines:
                if ',' in line:
                    k, v = line.split(',', 1)
                    st.session_state.temp_bulk.append({"Lokasi": k.strip().upper(), "Singkatan": v.strip().upper()})
            if st.session_state.temp_bulk:
                st.table(pd.DataFrame(st.session_state.temp_bulk))
        
        if cb2.button("💾 SIMPAN", type="primary", use_container_width=True):
            if st.session_state.temp_bulk:
                for item in st.session_state.temp_bulk:
                    st.session_state.mapping_lokasi[item["Lokasi"]] = item["Singkatan"]
                save_user_db(user_email, st.session_state.mapping_lokasi)
                st.session_state.temp_bulk = []
                st.success("Tersimpan!")
                st.rerun()

        st.divider()
        st.subheader("📊 Database Saat Ini")
        if st.session_state.mapping_lokasi:
            st.table(pd.DataFrame([{"Lokasi": k, "Singkatan": v} for k, v in st.session_state.mapping_lokasi.items()]))
            with st.expander("Hapus Data"):
                target = st.selectbox("Pilih Lokasi:", ["-- Pilih --"] + list(st.session_state.mapping_lokasi.keys()))
                if st.button("Hapus Permanen") and target != "-- Pilih --":
                    del st.session_state.mapping_lokasi[target]
                    save_user_db(user_email, st.session_state.mapping_lokasi)
                    st.rerun()

    elif menu == "📦 Backup & Restore":
        st.subheader("Export/Import JSON")
        js = json.dumps(st.session_state.mapping_lokasi, indent=4)
        st.download_button("📥 Download Backup", data=js, file_name="backup.json", mime="application/json", use_container_width=True)
        st.divider()
        up_file = st.file_uploader("Import JSON", type="json")
        if up_file:
            data_up = json.load(up_file)
            st.session_state.mapping_lokasi.update(data_up)
            save_user_db(user_email, st.session_state.mapping_lokasi)
            st.success("Berhasil Import!")
            st.rerun()

    st.divider()
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.connected = False
        st.rerun()

# --- 6. HALAMAN UTAMA (PROSES PDF & OCR) ---
st.title("🚀 Pemroses Nama Ceklis Sintelis")
selected_kode = st.selectbox("Pilih Kode Unit:", ["BPBKS1", "BPBKF1", "BPBYE1"])
use_ocr = st.checkbox("Gunakan OCR (Auto-Detect Aset)", value=False)
uploaded_files = st.file_uploader("Upload PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        for f in uploaded_files:
            name_only = os.path.splitext(f.name)[0]
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {f.name}: Tanggal tidak ditemukan.")
                continue
            
            tgl = tgl_match.group()
            tahun, bulan = tgl.split("-")[-1], int(tgl.split("-")[1])
            
            # Deteksi Lokasi (Anti-Spasi)
            found_short = None
            name_clean = name_only.upper().replace(" ", "")
            for k, v in st.session_state.mapping_lokasi.items():
                if k.replace(" ", "") in name_clean or v.replace(" ", "") in name_clean:
                    found_short = v
                    break
            
            if not found_short:
                st.error(f"❌ {f.name}: Lokasi tidak ada di database!")
                continue

            # Logika OCR untuk Aset
            assets = []
            if use_ocr:
                try:
                    images = convert_from_bytes(f.getvalue(), dpi=200)
                    raw_text = pytesseract.image_to_string(images[0])
                    # Regex mencari kata WESEL/SN/POLE diikuti angka
                    ocr_match = re.findall(r'(WESEL\s?\d+|SN\d+|POLE\s?\d+)', raw_text, re.IGNORECASE)
                    if ocr_match:
                        assets = [a.replace(" ", "_").upper() for a in ocr_match]
                except Exception as e:
                    st.error(f"OCR Error pada {f.name}: {e}")

            # Jika OCR gagal/dimatikan, pakai logika nama file lama
            if not assets:
                clean = name_only.upper().replace(tgl, "").replace(found_short, "").strip("_ ")
                parts = clean.split("_")
                for p in parts:
                    if any(char.isdigit() for char in p): assets.append(p.strip())
            
            if not assets:
                manual = st.text_input(f"Aset untuk {f.name}:", key=f"m_{f.name}")
                if manual: assets = [manual.strip()]
                else: continue

            for asset in assets:
                new_name = f"{tahun}-{bulan}_Resor 1.21 Boo_{selected_kode}_CEKLIS_{asset}_{found_short}_{tgl}.pdf"
                zip_f.writestr(new_name, f.getvalue())
                st.success(f"✅ {new_name}")

    st.divider()
    st.download_button("📥 Download ZIP Hasil", zip_buffer.getvalue(), "Hasil_Ceklis.zip", use_container_width=True)