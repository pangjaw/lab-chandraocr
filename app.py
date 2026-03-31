import streamlit as st
import re
import os
import zipfile
import json
from io import BytesIO
from streamlit_google_auth import Authenticate
from google.cloud import firestore
from google.oauth2 import service_account

import hashlib

def hash_password(password):
    # Mengubah password menjadi kode acak unik
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 2. KONEKSI FIRESTORE ---
# Di dalam bagian koneksi Firestore app.py
if "firebase" in st.secrets:
    key_dict = dict(st.secrets["firebase"])
    
    # PERBAIKAN: Mengubah teks \n menjadi baris baru yang asli
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict['project_id'])
else:
    st.error("Konfigurasi Firebase tidak ditemukan di Secrets!")
    st.stop()

# --- 3. FUNGSI DATABASE ---
def get_user_db(email):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("mapping", {})
    return {"BOGOR": "BOO"} # Default

def save_user_db(email, mapping):
    db.collection("users").document(email).set({"mapping": mapping})

# --- 4. LOGIKA LOGIN ---
## Inisialisasi status login jika belum ada
if 'connected' not in st.session_state:
    st.session_state.connected = False

if not st.session_state.connected:
    st.title("🔐 Login Ceklis Sintelis")
    
    # Input dari user
    email_input = st.text_input("Email/Username").lower().strip()
    pass_input = st.text_input("Password", type="password")
    
    col1, col2 = st.columns(2)
    
    # TOMBOL LOGIN
    if col1.button("Login", use_container_width=True):
        # Ambil data password dari koleksi 'credentials' di Firebase
        user_cred = db.collection("credentials").document(email_input).get()
        
        if user_cred.exists:
            stored_password = user_cred.to_dict().get("password")
            if hash_password(pass_input) == stored_password:
                st.session_state.connected = True
                st.session_state.user_email = email_input
                st.session_state.user_name = email_input.split("@")[0].upper()
                st.rerun()
            else:
                st.error("Password salah!")
        else:
            st.error("User tidak terdaftar!")

    # TOMBOL DAFTAR (Hanya untuk buat akun baru pertama kali)
    if col2.button("Daftar Akun Baru", use_container_width=True):
        if email_input and pass_input:
            db.collection("credentials").document(email_input).set({
                "password": hash_password(pass_input)
            })
            st.success("Akun berhasil dibuat! Silakan klik Login.")
        else:
            st.warning("Isi email dan password untuk mendaftar.")
            
    st.stop() # Hentikan script di sini jika belum login

# Jika sudah login, ambil info user
# Ganti bagian pengambilan email lama dengan ini:
user_email = st.session_state.user_email
user_name = st.session_state.user_name

# Database lokasi tetap diambil berdasarkan email yang login
if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)

# --- 5. CALLBACK DATABASE ---
def add_location_callback():
    val = st.session_state.input_baru
    if "=" in val:
        k, v = val.split("=")
        st.session_state.mapping_lokasi[k.strip().upper()] = v.strip().upper()
        save_user_db(user_email, st.session_state.mapping_lokasi)
        st.toast(f"Tersimpan: {k.strip().upper()}", icon="✅")
    st.session_state.input_baru = ""

def delete_location(key_to_delete):
    if key_to_delete in st.session_state.mapping_lokasi:
        del st.session_state.mapping_lokasi[key_to_delete]
        save_user_db(user_email, st.session_state.mapping_lokasi)
        st.toast(f"Dihapus: {key_to_delete}", icon="🗑️")

# --- 6. UI SIDEBAR ---
with st.sidebar:
    if user_info.get('picture'):
        st.image(user_info.get('picture'), width=50)
    st.write(f"Halo, **{user_info.get('name')}**")
    
    st.header("📍 Database Lokasi")
    st.text_input("Tambah (LOKASI=KODE lalu Enter)", key="input_baru", on_change=add_location_callback)
    
    st.divider()
    st.subheader("Daftar Lokasi")
    for k, v in list(st.session_state.mapping_lokasi.items()):
        col1, col2 = st.columns([3, 1])
        col1.write(f"**{k}** → {v}")
        if col2.button("❌", key=f"del_{k}"):
            delete_location(k)
            st.rerun()
            
    st.divider()
    if st.button("Log Out", use_container_width=True):
    st.session_state.connected = False
    st.session_state.user_email = None
    st.rerun()

# --- 7. HALAMAN UTAMA: PROSES FILE ---
st.title("🚀 Pemroses Nama Ceklis")
kode_opsi = ["BPBKS1", "BPBKF1", "BPBYE1"]
selected_kode = st.selectbox("Pilih Kode Unit:", kode_opsi)

uploaded_files = st.file_uploader("Upload PDF (Bisa banyak sekaligus)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    # Gunakan mode 'w' untuk ZIP baru
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for uploaded_file in uploaded_files:
            name_only = os.path.splitext(uploaded_file.name)[0]
            
            # Cari Tanggal
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {name_only}: Tanggal tidak ditemukan.")
                continue
            
            tgl = tgl_match.group()
            tahun = tgl.split("-")[-1]
            bulan = int(tgl.split("-")[1])

            # --- LOGIKA LOKASI (ANTI-SPASI) ---
            found_full, found_short = None, None
            name_no_space = name_only.upper().replace(" ", "")

            for k, v in st.session_state.mapping_lokasi.items():
                key_no_space = k.upper().replace(" ", "")
                val_no_space = v.upper().replace(" ", "")
                
                if key_no_space in name_no_space or val_no_space in name_no_space:
                    found_full, found_short = k, v
                    break
            
            if not found_short:
                st.error(f"❌ {name_only}: Lokasi tidak ada di database!")
                continue

            # Logika Pemisahan Aset & Perawatan
            clean = name_only.upper().replace(tgl, "").replace(str(found_full), "").replace(str(found_short), "").strip("_ ")
            parts = clean.split("_")
            perawatan_parts, assets = [], []

            for p in parts:
                p = p.strip()
                if "," in p:
                    assets.extend([a.strip() for a in p.split(",") if a.strip()])
                elif any(char.isdigit() for char in p) and not any(x in p for x in ["MINGGUAN", "BULANAN", "TAHUNAN"]):
                    assets.append(p)
                elif p != "":
                    perawatan_parts.append(p)
            
            # Input aset manual jika tidak terdeteksi
            if not assets:
                manual_a = st.text_input(f"Aset untuk {name_only} (pisah koma):", key=f"m_{name_only}")
                if manual_a:
                    assets = [a.strip() for a in manual_a.split(",")]
                else:
                    continue

            nama_perawatan = "_".join(perawatan_parts).replace(" ", "_").strip("_")

            # Bungkus ke dalam ZIP
            for asset in assets:
                new_name = f"{tahun}-{bulan}_Resor 1.21 Boo_{selected_kode}_{nama_perawatan}_{asset}_{found_short}_{tgl}.pdf"
                zip_file.writestr(new_name, uploaded_file.getvalue())
                st.success(f"Berhasil diproses: {new_name}")

    st.divider()
    st.download_button(
        label="📥 Download Semua File (.ZIP)",
        data=zip_buffer.getvalue(),
        file_name="Ceklis_Sintelis_Done.zip",
        use_container_width=True
    )
