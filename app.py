import streamlit as st
import json
import re
import os
import zipfile
import platform
import pytesseract
import time
from io import BytesIO
from pdf2image import convert_from_bytes
from streamlit_lottie import st_lottie

# --- 1. KONFIGURASI OCR ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def load_lottiefile(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return None

# NAMA JSON: Metro Rail.json
lottie_train = load_lottiefile("Metro Rail.json")

# --- 2. TAMPILAN UTAMA ---
st.set_page_config(page_title="Ganti Nama File Ceklis Sintelis", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📁 Input & Setting")
    use_ocr = st.checkbox("Gunakan OCR Otomatis", value=True)
    uploaded_files = st.file_uploader("Upload PDF", type="pdf", accept_multiple_files=True)

# --- 3. PROSES DATA ---
if uploaded_files:
    zip_buffer = BytesIO()
    processed_files = []
    
    with col2:
        st.subheader("📋 Hasil Proses")
        placeholder = st.empty()
        
        with placeholder.container():
            if lottie_train:
                st_lottie(lottie_train, height=150, key="train_loader")
            st.info("🚂 Sedang mengambil data Aset & Lokasi dari Foto Dokumentasi...")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for f in uploaded_files:
                name_only = os.path.splitext(f.name)[0]
                
                # Ambil Tanggal dari nama file asli (DD-MM-YYYY)
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                tgl = tgl_match.group() if tgl_match else "00-00-0000"

                final_location = "LOKASI_TIDAK_TERDETEKSI"
                asset_name = "ASET"
                is_persinyalan_elektrik = False
                
                try:
                    # Convert halaman (limit 10 halaman)
                    images = convert_from_bytes(f.getvalue(), dpi=150, last_page=10)
                    
                    target_page_text = ""
                    text_h1 = pytesseract.image_to_string(images[0]).upper()
                    
                    # CEK JENIS FILE DI HALAMAN 1
                    if "PERALATAN DALAM PERSINYALAN ELEKTRIK" in text_h1:
                        is_persinyalan_elektrik = True

                    # CARI HALAMAN FOTO DOKUMENTASI
                    for img in images:
                        current_text = pytesseract.image_to_string(img).upper()
                        if "FOTO DOKUMENTASI" in current_text:
                            target_page_text = current_text
                            break
                    
                    # Failsafe jika tidak ada halaman foto, pakai hal 1
                    if not target_page_text:
                        target_page_text = text_h1

                    # --- 1. LOGIKA [ASET] ---
                    if is_persinyalan_elektrik:
                        asset_name = "PDSE" # Jika terdeteksi Peralatan Dalam, Aset = PDSE
                    else:
                        # Untuk ceklis biasa, cari nama alat (Wesel, Sinyal, dll) di halaman target
                        match_aset = re.findall(r'(?:WESEL|BLOK|SINYAL|COUNTER)\s+([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)', target_page_text, re.IGNORECASE)
                        if not match_aset: # Backup cek ke halaman 1
                            match_aset = re.findall(r'(?:WESEL|BLOK|SINYAL|COUNTER)\s+([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)', text_h1, re.IGNORECASE)
                        
                        asset_name = match_aset[0].upper().replace(".", "").replace(" ", "") if match_aset else "ASET"

                    # --- 2. LOGIKA [LOKASI] ---
                    if is_persinyalan_elektrik:
                        # Ambil nama lokasi utuh dari halaman Foto Dokumentasi
                        loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s]{3,20})', target_page_text)
                        if loc_match:
                            final_location = loc_match.group(1).strip().split('\n')[0]
                        else:
                            stations = ["BOGOR", "CILEBUT", "BOJONG GEDE", "CITAYAM", "DEPOK", "MANGGARAI", "JAKARTA KOTA"]
                            for s in stations:
                                if s in target_page_text:
                                    final_location = s
                                    break
                    else:
                        # Ceklis biasa: Pakai singkatan (BOO, MRI, dll)
                        loc_pair = re.search(r'([A-Z]{3,4}\-[A-Z]{3,4})', target_page_text)
                        loc_single = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB|SI|CCL|BGR)\b', target_page_text)
                        if loc_pair: final_location = loc_pair.group()
                        elif loc_single: final_location = loc_single[0]

                except:
                    continue

                # --- FORMAT FINAL: PERAWATAN [ASET] [LOKASI] [TANGGAL] ---
                new_name = f"PERAWATAN {asset_name} {final_location} {tgl}.pdf"
                
                zip_f.writestr(new_name, f.getvalue())
                processed_files.append(new_name)

        placeholder.empty()

        if processed_files:
            with st.container(height=250):
                for p_file in processed_files:
                    st.write(f"✅ `{p_file}`")
            
            st.download_button(
                label="📥 DOWNLOAD HASIL (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Hasil_Rename_Sintelis.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis KAI Utility</div>", unsafe_allow_html=True)