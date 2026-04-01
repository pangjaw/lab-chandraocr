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
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- 2. FUNGSI KEAMANAN & DATABASE ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

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

# --- 4. SESSION STATE ---
user_email = st.session_state.user_email
user_name = st.session_state.user_name

if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)
if 'temp_bulk' not in st.session_state:
    st.session_state.temp_bulk = []

# --- 5. SIDEBAR (KONTROL DATABASE) ---
with st.sidebar:
    st.write(f"Halo, **{user_name}**")
    menu = st.radio("Pilih Menu:", ["📍 Kelola Lokasi", "📦 Backup & Restore"])
    st.divider()

    if menu == "📍 Kelola Lokasi":
        st.subheader("🚀 Bulk Input")
        bulk_area = st.text_area("Paste (LOKASI,KODE):", height=150, placeholder="BOGOR,BOO\nDEPOK,DP")
        cb1, cb2 = st.columns(2)
        if cb1.button("🧐 Pratinjau", use_container_width=True):
            lines = bulk_area.strip().split('\n')
            st.session_state.temp_bulk = [{"Lokasi": l.split(',')[0].strip().upper(), "Singkatan": l.split(',')[1].strip().upper()} for l in lines if ',' in l]
            if st.session_state.temp_bulk: st.table(pd.DataFrame(st.session_state.temp_bulk))
        
        if cb2.button("💾 SIMPAN", type="primary", use_container_width=True):
            if st.session_state.temp_bulk:
                for item in st.session_state.temp_bulk: st.session_state.mapping_lokasi[item["Lokasi"]] = item["Singkatan"]
                save_user_db(user_email, st.session_state.mapping_lokasi)
                st.session_state.temp_bulk = []
                st.success("Tersimpan!")
                st.rerun()

    elif menu == "📦 Backup & Restore":
        js = json.dumps(st.session_state.mapping_lokasi, indent=4)
        st.download_button("📥 Download Backup", data=js, file_name="backup.json", mime="application/json", use_container_width=True)
        up_file = st.file_uploader("Import JSON", type="json")
        if up_file:
            st.session_state.mapping_lokasi.update(json.load(up_file))
            save_user_db(user_email, st.session_state.mapping_lokasi)
            st.rerun()

    st.divider()
    if st.button("🚪 Log Out", use_container_width=True):
        st.session_state.connected = False
        st.rerun()

# --- 6. HALAMAN UTAMA (FORMAT BARU) ---
st.title("🚀 Pemroses Nama Ceklis")
st.info("Format Baru: PERAWATAN [ASET] [LOKASI] [TANGGAL]")

use_ocr = st.checkbox("Gunakan OCR (Deteksi Otomatis Nomor Aset)", value=True)
uploaded_files = st.file_uploader("Upload PDF (Banyak sekaligus)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        for f in uploaded_files:
            name_only = os.path.splitext(f.name)[0]
            
            # 1. Cari Tanggal
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {f.name}: Tanggal tidak ditemukan.")
                continue
            tgl = tgl_match.group()
            
            # 2. Cari Lokasi (Anti-Spasi)
            found_short = None
            name_clean = name_only.upper().replace(" ", "")
            for k, v in st.session_state.mapping_lokasi.items():
                if k.replace(" ", "") in name_clean or v.replace(" ", "") in name_clean:
                    found_short = v
                    break
            
            if not found_short:
                st.error(f"❌ {f.name}: Lokasi tidak terdaftar di database!")
                continue

            # 3. Cari Aset (OCR atau Nama File)
        
            # --- LOGIKA OCR FOKUS AREA ---
            assets = []
            found_short = None
            
            if use_ocr:
                try:
                    # Ambil halaman pertama dengan DPI tinggi
                    images = convert_from_bytes(f.getvalue(), dpi=300)
                    img = images[0]
                    width, height = img.size

                    # --- STRATEGI CROP (Hanya ambil area kanan atas) ---
                    # Kita potong gambar: Ambil 50% lebar kanan, dan 40% tinggi atas
                    # Area ini adalah tempat daftar aset ZP/B/W biasanya berada
                    left = width * 0.45  # Mulai dari hampir tengah ke kanan
                    top = height * 0.15   # Mulai sedikit di bawah margin atas
                    right = width * 0.95 # Sampai pinggir kanan
                    bottom = height * 0.5 # Hanya sampai setengah halaman (hindari tabel bawah)
                    
                    img_cropped = img.crop((left, top, right, bottom))
                    
                    # Jalankan OCR hanya pada potongan gambar tersebut
                    raw_text = pytesseract.image_to_string(img_cropped)

                    # 1. AMBIL NOMOR ASET (B, W, ZP, UB, dll)
                    ocr_match = re.findall(r'\b([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)\b', raw_text, re.IGNORECASE)
                    
                    if ocr_match:
                        cleaned_list = [a.upper().replace(".", "").replace(" ", "") for a in ocr_match]
                        unique_assets = []
                        for item in cleaned_list:
                            if item not in unique_assets:
                                unique_assets.append(item)
                        assets = unique_assets[:5]

                    # 2. AMBIL LOKASI (CLT-BOO)
                    # Kita scan seluruh halaman untuk lokasi karena letaknya bisa bervariasi
                    full_text = pytesseract.image_to_string(img)
                    loc_match = re.search(r'([A-Z]{3,4}\-[A-Z]{3,4})', full_text)
                    if loc_match:
                        found_short = loc_match.group().upper()
                        
                except Exception as e:
                    st.error(f"OCR Error: {e}")

            # 4. Input Manual Jika Benar-benar Tidak Ketemu
            if not assets:
                manual = st.text_input(f"Aset tidak terdeteksi untuk {f.name}:", key=f"m_{f.name}")
                if manual: assets = [manual.upper().strip()]
                else: continue

            # 5. Bungkus ke ZIP dengan Nama Baru
            for asset in list(dict.fromkeys(assets)): # Hapus duplikat
                new_name = f"PERAWATAN {asset} {found_short} {tgl}.pdf"
                zip_f.writestr(new_name, f.getvalue())
                st.success(f"✅ Siap: {new_name}")

    st.divider()
    if st.button("📥 DOWNLOAD SEMUA HASIL (.ZIP)", use_container_width=True, type="primary"):
        st.download_button("Klik di sini untuk mengunduh", zip_buffer.getvalue(), "Hasil_Ceklis_Sintelis.zip", use_container_width=True)