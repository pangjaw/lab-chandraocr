import streamlit as st
import re
import os
import zipfile
from io import BytesIO
from google.cloud import firestore
from google.oauth2 import service_account
import json

# --- KONEKSI KE FIRESTORE ---
# Simpan isi file JSON dari Firebase tadi ke Streamlit Secrets
if "firebase" in st.secrets:
    key_dict = json.loads(st.secrets["firebase"]["key"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict['project_id'])
else:
    st.error("Silakan masukkan Firebase Key di Streamlit Secrets!")
    st.stop()

# --- FUNGSI DATABASE ---
def get_user_db(email):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("mapping", {"BOGOR": "BOO"})
    return {"BOGOR": "BOO"}

def save_user_db(email, mapping):
    db.collection("users").document(email).set({"mapping": mapping})

# --- SIMULASI LOGIN (UNTUK DEMO STREAMLIT) ---
# Catatan: Untuk Google Login sungguhan di Streamlit, 
# biasanya menggunakan library 'streamlit-google-auth'
st.title("📝 Ceklis Sintelis Pro")

if 'user_email' not in st.session_state:
    st.info("Silakan Login untuk mengakses database lokasi Anda.")
    # Ini adalah simulasi, di versi deploy gunakan st.login
    email_input = st.text_input("Masukkan Email Google Anda untuk Demo:")
    if st.button("Masuk"):
        st.session_state.user_email = email_input.lower()
        st.rerun()
    st.stop()

# --- JIKA SUDAH LOGIN ---
user_email = st.session_state.user_email
if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)

st.sidebar.write(f"Logged in as: **{user_email}**")
if st.sidebar.button("Logout"):
    del st.session_state.user_email
    del st.session_state.mapping_lokasi
    st.rerun()

# --- UI SETTINGS LOKASI ---
with st.sidebar.expander("Edit Database Lokasi"):
    new_input = st.text_input("Tambah (Contoh: MASENG=MSG)")
    if st.button("Simpan Ke Awan"):
        if "=" in new_input:
            k, v = new_input.split("=")
            st.session_state.mapping_lokasi[k.strip().upper()] = v.strip().upper()
            save_user_db(user_email, st.session_state.mapping_lokasi)
            st.success("Tersimpan secara permanen!")

# --- LOGIKA PROSES FILE (SAMA SEPERTI SEBELUMNYA) ---
kode_opsi = ["BPBKS1", "BPBKF1", "BPBYE1"]
selected_kode = st.selectbox("Pilih Kode Unit:", kode_opsi)

uploaded_files = st.file_uploader("Upload PDF Ceklis", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        for uploaded_file in uploaded_files:
            name_only = os.path.splitext(uploaded_file.name)[0]
            
            # Logika Regex Tanggal
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match: continue
            
            tgl = tgl_match.group()
            tahun, bulan = tgl.split("-")[-1], int(tgl.split("-")[1])

            # Cari Lokasi dari database session_state
            found_short = next((st.session_state.mapping_lokasi[k] for k in st.session_state.mapping_lokasi if k in name_only.upper()), None)
            
            if not found_short:
                st.warning(f"Lokasi {name_only} belum terdaftar.")
                continue

            # Logika Pemisahan Aset
            # (Gunakan logika pemisahan aset dari kode sebelumnya di sini)
            # ... [Bagian Logika Aset] ...
            
            # Simulasi simpan hasil
            new_name = f"{tahun}-{bulan}_Resor_1.21_{selected_kode}_{found_short}_{tgl}.pdf"
            zip_file.writestr(new_name, uploaded_file.getvalue())

    st.download_button("📥 Download Hasil (.ZIP)", zip_buffer.getvalue(), "Hasil.zip")
