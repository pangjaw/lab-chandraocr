import streamlit as st
import re
import os
import zipfile
import json
from io import BytesIO
from streamlit_google_auth import Authenticate
from google.cloud import firestore
from google.oauth2 import service_account

# --- 1. KONFIGURASI GOOGLE AUTH ---
# Ambil data dari Secrets Streamlit Cloud
GOOGLE_CLIENT_ID = st.secrets["google_auth"]["client_id"]
GOOGLE_CLIENT_SECRET = st.secrets["google_auth"]["client_secret"]
REDIRECT_URI = st.secrets["google_auth"]["redirect_uri"]

# Masukkan variabel di atas ke dalam Authenticate
authenticator = Authenticate(
    secret_key=st.secrets["google_auth"]["secret_key"], # Pastikan di Secrets ada ini
    cookie_name="google_auth_cookie",
    cookie_expiry_days=30,
    client_id=st.secrets["google_auth"]["client_id"],
    client_secret=st.secrets["google_auth"]["client_secret"],
    redirect_uri=st.secrets["google_auth"]["redirect_uri"],
)

# Perbaikan Typo: Bukan check_authenticator(), tapi check_authentification()
authenticator.check_authentification()

# --- 2. KONEKSI FIRESTORE ---
if "firebase" in st.secrets:
    key_dict = json.loads(st.secrets["firebase"]["key"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict['project_id'])
else:
    st.error("Masukkan Firebase Key di Streamlit Secrets!")
    st.stop()

# --- 3. FUNGSI DATABASE ---
def get_user_db(email):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("mapping", {})
    return {"BOGOR": "BOO"} # Default jika user baru

def save_user_db(email, mapping):
    db.collection("users").document(email).set({"mapping": mapping})

# --- 4. LOGIKA LOGIN ---
if not st.session_state.get('connected'):
    st.title("📝 Ceklis Sintelis Pro")
    st.write("Selamat datang! Silakan login dengan akun Google kantor Anda.")
    authenticator.login()
    st.stop() # Sangat penting agar kode di bawah tidak error karena user_info kosong

# Jika sudah login, ambil info user
user_info = st.session_state.get('user_info')
if user_info:
    user_email = user_info.get('email').lower()
else:
    st.error("Gagal mengambil data profil.")
    st.stop()

if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)

# --- 5. FUNGSI CALLBACK & DATABASE MANAGEMENT ---
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
    
    st.header(f"📍 Database Lokasi")
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
        authenticator.logout()
        st.rerun()

# --- 7. HALAMAN UTAMA: PROSES FILE ---
st.title("🚀 Pemroses Nama Ceklis")
kode_opsi = ["BPBKS1", "BPBKF1", "BPBYE1"]
selected_kode = st.selectbox("Pilih Kode Unit:", kode_opsi)

uploaded_files = st.file_uploader("Drag & Drop PDF di sini", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file: # Gunakan "w" untuk buat baru
        for uploaded_file in uploaded_files:
            name_only = os.path.splitext(uploaded_file.name)[0]
            
            # Cari Tanggal
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {name_only}: Tanggal tidak ditemukan.")
                continue
            
            tgl = tgl_match.group()
            tahun, bulan = tgl.split("-")[-1], int(tgl.split("-")[1])

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

            # Logika Pemisahan Aset
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
            
            if not assets:
                manual_a = st.text_input(f"Aset untuk {name_only} (pisah koma):", key=f"m_{name_only}")
                if manual_a:
                    assets = [a.strip() for a in manual_a.split(",")]
                else: continue

            nama_perawatan = "_".join(perawatan_parts).replace(" ", "_").strip("_")

            # Bungkus ke ZIP
            for asset in assets:
                new_name = f"{tahun}-{bulan}_Resor 1.21 Boo_{selected_kode}_{nama_perawatan}_{asset}_{found_short}_{tgl}.pdf"
                zip_file.writestr(new_name, uploaded_file.getvalue())
                st.success(f"Dibuat: {new_name}")

            # Pindahkan download button ke dalam blok 'if uploaded_files'
    st.download_button(
        label="📥 Download ZIP", 
        data=zip_buffer.getvalue(), 
        file_name="Ceklis_Done.zip", 
        use_container_width=True
    )
    st.divider()
    st.download_button("📥 Download ZIP", zip_buffer.getvalue(), "Ceklis_Done.zip", use_container_width=True)
