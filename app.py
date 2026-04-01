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

# --- 1. KONFIGURASI OCR ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- 2. FUNGSI DATABASE (FIREBASE) ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

if "firebase" in st.secrets:
    key_dict = dict(st.secrets["firebase"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict['project_id'])
else:
    st.error("Konfigurasi Firebase tidak ditemukan!")
    st.stop()

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
            st.session_state.connected, st.session_state.user_email = True, email_in
            st.rerun()
        else: st.error("Login Gagal!")
    if c2.button("Daftar Baru", use_container_width=True):
        if email_in and pass_in:
            db.collection("credentials").document(email_in).set({"password": hash_password(pass_in)})
            st.success("Berhasil! Silakan Login.")
    st.stop()

# --- 4. HALAMAN UTAMA ---
st.title("🚀 Pemroses Ceklis Sintelis")
st.info("Format: PERAWATAN [ASET] [LOKASI] [TANGGAL]")

use_ocr = st.checkbox("Gunakan OCR (Deteksi Otomatis)", value=True)
uploaded_files = st.file_uploader("Upload PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        for f in uploaded_files:
            name_only = os.path.splitext(f.name)[0]
            
            # 1. AMBIL TANGGAL DARI NAMA FILE
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {f.name}: Tanggal tidak ada.")
                continue
            tgl = tgl_match.group()

            assets = []
            found_short = "LOKASI_TIDAK_TERDETEKSI"
            
            try:
                # 2. PROSES GAMBAR UNTUK OCR
                images = convert_from_bytes(f.getvalue(), dpi=300)
                img = images[0]
                width, height = img.size

                if use_ocr:
                    # --- A. DETEKSI ASET (CROP KANAN ATAS) ---
                    # Geser left ke 0.55 agar tidak baca nomor urut di kiri tabel
                    left, top, right, bottom = width*0.55, height*0.05, width*0.98, height*0.55
                    img_cropped = img.crop((left, top, right, bottom))
                    text_aset = pytesseract.image_to_string(img_cropped)
                    
                    # Regex mencari kode setelah kata kunci (Sinyal/Wesel/Counter)
                    match_aset = re.findall(r'(?:WESEL|BLOK|SINYAL|COUNTER)\s+([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)', text_aset, re.IGNORECASE)
                    
                    if match_aset:
                        # Bersihkan Titik & Spasi (B.112 -> B112)
                        cleaned = [a.upper().replace(".", "").replace(" ", "") for a in match_aset]
                        # Hapus duplikat & Limit 5
                        for item in cleaned:
                            if item not in assets: assets.append(item)
                        assets = assets[:5]

                    # --- B. DETEKSI LOKASI (FULL SCAN) ---
                    full_text = pytesseract.image_to_string(img).upper()
                    
                    # Pola 1: CLT-BOO
                    loc_pair = re.search(r'([A-Z]{3,4}\-[A-Z]{3,4})', full_text)
                    # Pola 2: Singkatan Tunggal (Daftar Stasiun)
                    loc_single = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB)\b', full_text)

                    if loc_pair: found_short = loc_pair.group().upper()
                    elif loc_single: found_short = loc_single[0]
                    # Pola 3: Nama Panjang Bogor -> BOO (Fallback)
                    elif "BOGOR" in full_text: found_short = "BOO"

            except Exception as e:
                st.error(f"Error {f.name}: {e}")
                continue

            # 3. FALLBACK & PENAMAAN
            if not assets: # Jika OCR gagal, ambil dari nama file asli
                assets = [p for p in name_only.upper().split("_") if any(c.isdigit() for c in p)][:1]
            
            if not assets:
                st.warning(f"Aset {f.name} tidak ketemu, dilewati.")
                continue

            for asset in assets:
                new_name = f"PERAWATAN {asset} {found_short} {tgl}.pdf"
                zip_f.writestr(new_name, f.getvalue())
                st.success(f"✅ {new_name}")

    st.divider()
    if st.button("📥 DOWNLOAD SEMUA HASIL (.ZIP)", use_container_width=True, type="primary"):
        st.download_button("Klik untuk Unduh", zip_buffer.getvalue(), "Ceklis_Sintelis_Fix.zip", use_container_width=True)