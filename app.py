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

lottie_train = load_lottiefile("train_loading.json")

# --- 2. TAMPILAN UTAMA ---
st.set_page_config(page_title="Ganti Nama File Ceklis Sintelis", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📁 Input & Setting")
    use_ocr = st.checkbox("Gunakan OCR Otomatis", value=True)
    uploaded_files = st.file_uploader("Upload PDF (Ceklis Biasa / Peralatan Dalam)", type="pdf", accept_multiple_files=True)

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
            st.info("🚂 Sedang menyisir data Peralatan Dalam Sinyal Elektrik...")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for f in uploaded_files:
                name_only = os.path.splitext(f.name)[0]
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                tgl = tgl_match.group() if tgl_match else "00-00-0000"

                found_short = "LOKASI_TIDAK_TERDETEKSI"
                asset_name = "PDSE" # Default jika peralatan dalam
                
                try:
                    # Convert minimal 2 halaman pertama
                    images = convert_from_bytes(f.getvalue(), dpi=200, last_page=2)
                    
                    # Scan Halaman 1 untuk identifikasi jenis ceklis
                    text_page_1 = pytesseract.image_to_string(images[0]).upper()
                    
                    # Logika Pencarian: PERALATAN DALAM SINYAL ELEKTRIK
                    is_pdse = "PERALATAN DALAM SINYAL ELEKTRIK" in text_page_1 or "PDSE" in text_page_1
                    
                    # Tentukan halaman mana yang akan diambil lokasinya
                    if is_pdse and len(images) >= 2:
                        page_for_location = images[1] # Fokus ke Halaman 2
                    else:
                        page_for_location = images[0] # Fokus ke Halaman 1

                    # Jalankan OCR pada halaman target
                    text_target = pytesseract.image_to_string(page_for_location).upper()

                    # A. DETEKSI LOKASI (Singkatan Stasiun)
                    loc_pair = re.search(r'([A-Z]{3,4}\-[A-Z]{3,4})', text_target)
                    loc_single = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB|SI|CCL|BGR)\b', text_target)

                    if loc_pair: found_short = loc_pair.group()
                    elif loc_single: found_short = loc_single[0]
                    elif "BOGOR" in text_target: found_short = "BOO"

                    # B. DETEKSI ASET
                    if not is_pdse:
                        match_aset = re.findall(r'(?:WESEL|BLOK|SINYAL|COUNTER)\s+([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)', text_target, re.IGNORECASE)
                        asset_name = match_aset[0].upper().replace(".", "").replace(" ", "") if match_aset else "ASET"
                    else:
                        # Untuk PDSE, kita bisa ambil dari nama file asli jika ada kodenya
                        file_code = [p for p in name_only.upper().split("_") if any(c.isdigit() for c in p)]
                        asset_name = file_code[0] if file_code else "PDSE"

                except:
                    continue

                # Gabungkan Nama
                prefix = "PDSE" if is_pdse else "PERAWATAN"
                new_name = f"{prefix} {asset_name} {found_short} {tgl}.pdf"
                
                zip_f.writestr(new_name, f.getvalue())
                processed_files.append(new_name)

        placeholder.empty()

        if processed_files:
            with st.container(height=250):
                for p_file in processed_files:
                    st.write(f"✅ `{p_file}`")
            
            st.download_button(
                label="📥 DOWNLOAD (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Hasil_Rename_Sintelis.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis KAI Utility</div>", unsafe_allow_html=True)