import streamlit as st
import re
import os
import zipfile
import json
from io import BytesIO
from streamlit_google_auth import Authenticate # Library baru
from google.cloud import firestore
from google.oauth2 import service_account

# --- 1. KONFIGURASI GOOGLE AUTH ---
# Masukkan Client ID yang didapat dari Google Cloud Console
GOOGLE_CLIENT_ID = "MASUKKAN_CLIENT_ID_ANDA.apps.googleusercontent.com"

authenticator = Authenticate(
    client_id=GOOGLE_CLIENT_ID,
    client_secret="NOT_REQUIRED_FOR_THIS_LIB", # Bisa diisi sembarang
    redirect_uri="https://nama-app-kamu.streamlit.app", # Sesuaikan dengan URL web kamu
    cookie_name="google_auth_cookie",
    key="secret_cookie_key",
    cookie_duration_days=30,
)

# Cek apakah user sudah login sebelumnya (via cookie)
authenticator.check_authenticator()

# --- 2. KONEKSI FIRESTORE (Database) ---
if "firebase" in st.secrets:
    key_dict = json.loads(st.secrets["firebase"]["key"])
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict['project_id'])
else:
    st.error("Masukkan Firebase Key di Streamlit Secrets!")
    st.stop()

def get_user_db(email):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    return doc.to_dict().get("mapping", {"BOGOR": "BOO"}) if doc.exists else {"BOGOR": "BOO"}

def save_user_db(email, mapping):
    db.collection("users").document(email).set({"mapping": mapping})

# --- 3. TAMPILAN HALAMAN LOGIN ---
if not st.session_state.get('connected'):
    st.title("📝 Ceklis Sintelis Pro")
    st.write("Selamat datang! Silakan login dengan akun Google kantor Anda.")
    
    # Tombol Login Google Asli
    authenticator.login()
    st.stop()

# --- 4. JIKA SUDAH BERHASIL LOGIN ---
# Mengambil info email dari Google
user_info = st.session_state.get('user_info')
user_email = user_info.get('email').lower()

if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)

# Tampilan Sidebar dengan Nama & Foto Profil (Opsional)
with st.sidebar:
    if user_info.get('picture'):
        st.image(user_info.get('picture'), width=50)
    st.write(f"Halo, **{user_info.get('name')}**")
    st.caption(user_email)
    
    if st.button("Log Out"):
        authenticator.logout()
        st.rerun()
    st.divider()

# --- 5. LANJUTKAN DENGAN LOGIKA DATABASE & PROSES FILE ---
# (Gunakan fungsi add_location_callback dan proses file yang sebelumnya di sini)
# ...

# --- FUNGSI DATABASE ---
def get_user_db(email):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("mapping", {})
    return {"BOGOR": "BOO"}

def save_user_db(email, mapping):
    db.collection("users").document(email).set({"mapping": mapping})

# --- LOGIN SESSION ---
if 'user_email' not in st.session_state:
    st.title("📝 Ceklis Sintelis Login")
    email_input = st.text_input("Masukkan Email Google:")
    if st.button("Masuk"):
        st.session_state.user_email = email_input.lower()
        st.rerun()
    st.stop()

user_email = st.session_state.user_email

# Load data awal jika belum ada di session
if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)

# --- FUNGSI CALLBACK (ENTER TO SAVE & CLEAR) ---
def add_location_callback():
    val = st.session_state.input_baru
    if "=" in val:
        k, v = val.split("=")
        st.session_state.mapping_lokasi[k.strip().upper()] = v.strip().upper()
        # Simpan ke Firestore
        save_user_db(user_email, st.session_state.mapping_lokasi)
        st.toast(f"Tersimpan: {k.strip().upper()}", icon="✅")
    # Reset input box
    st.session_state.input_baru = ""

def delete_location(key_to_delete):
    if key_to_delete in st.session_state.mapping_lokasi:
        del st.session_state.mapping_lokasi[key_to_delete]
        save_user_db(user_email, st.session_state.mapping_lokasi)
        st.toast(f"Dihapus: {key_to_delete}", icon="🗑️")

# --- UI SIDEBAR: DATABASE ---
with st.sidebar:
    st.header(f"📍 Database {user_email}")
    
    # Input Box (Enter to Save)
    st.text_input(
        "Tambah Lokasi (BOGOR=BOO lalu Enter)", 
        key="input_baru", 
        on_change=add_location_callback
    )
    
    st.divider()
    st.subheader("Daftar Lokasi")
    
    # Menampilkan List dengan Tombol Hapus
    if not st.session_state.mapping_lokasi:
        st.info("Database kosong.")
    else:
        for k, v in list(st.session_state.mapping_lokasi.items()):
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{k}** → {v}")
            if col2.button("❌", key=f"del_{k}"):
                delete_location(k)
                st.rerun()

    if st.sidebar.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# --- HALAMAN UTAMA: PROSES FILE ---
st.title("🚀 Pemroses Nama Ceklis")
kode_opsi = ["BPBKS1", "BPBKF1", "BPBYE1"]
selected_kode = st.selectbox("Pilih Kode Unit:", kode_opsi)

uploaded_files = st.file_uploader("Drag & Drop PDF di sini", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        for uploaded_file in uploaded_files:
            name_only = os.path.splitext(uploaded_file.name)[0]
            
            # Cari Tanggal
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {name_only}: Tanggal tidak ditemukan.")
                continue
            
            tgl = tgl_match.group()
            tahun, bulan = tgl.split("-")[-1], int(tgl.split("-")[1])

            # Cari Lokasi
           # --- LOGIKA LOKASI (ANTI-SPASI) ---
            found_full = None
            found_short = None
            
            # Buat versi nama file tanpa spasi untuk pengecekan
            name_no_space = name_only.upper().replace(" ", "")

            for k, v in st.session_state.mapping_lokasi.items():
                # Buat versi key database tanpa spasi
                key_no_space = k.upper().replace(" ", "")
                val_no_space = v.upper().replace(" ", "")
                
                # Cek apakah key (tanpa spasi) ada di dalam nama file (tanpa spasi)
                if key_no_space in name_no_space or val_no_space in name_no_space:
                    found_full, found_short = k, v
                    break
            
            if not found_short:
                st.error(f"❌ {name_only}: Lokasi tidak ada di database!")
                continue

            # Logika Pemisahan Aset & Nama Perawatan
            clean = name_only.upper().replace(tgl, "").replace(str(found_full), "").replace(str(found_short), "").strip("_ ")
            parts = clean.split("_")
            perawatan_parts = []
            assets = []

            for p in parts:
                p = p.strip()
                if "," in p:
                    assets.extend([a.strip() for a in p.split(",") if a.strip()])
                elif any(char.isdigit() for char in p) and not any(x in p for x in ["MINGGUAN", "BULANAN", "TAHUNAN"]):
                    assets.append(p)
                elif p != "":
                    perawatan_parts.append(p)
            
            # Tanya aset jika kosong
            if not assets:
                manual_a = st.text_input(f"Aset untuk {name_only} (pisah koma):", key=f"m_{name_only}")
                if manual_a:
                    assets = [a.strip() for a in manual_a.split(",")]
                else:
                    continue

            nama_perawatan = "_".join(perawatan_parts).replace(" ", "_").strip("_")

            # Bungkus ke ZIP
            for asset in assets:
                new_name = f"{tahun}-{bulan}_Resor 1.21 Boo_{selected_kode}_{nama_perawatan}_{asset}_{found_short}_{tgl}.pdf"
                zip_file.writestr(new_name, uploaded_file.getvalue())
                st.success(f"Dibuat: {new_name}")

    st.divider()
    st.download_button(
        "📥 Download Semua File (.ZIP)", 
        zip_buffer.getvalue(), 
        "Ceklis_Sintelis_Done.zip",
        use_container_width=True
    )
