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

# --- 1. KONFIGURASI & FUNGSI LOADING ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def load_lottiefile(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return None

# Load file JSON animasi kereta
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
            st.info("🚂 Sedang memproses data Sintelis...")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for f in uploaded_files:
                name_only = os.path.splitext(f.name)[0].upper()
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                if not tgl_match: continue
                tgl = tgl_match.group()

                assets = []
                found_short = "LOKASI_TIDAK_TERDETEKSI"

                # CEK APAKAH FILE UTAMA (AXLE, SINYAL, WESEL)
                if any(x in name_only for x in ["AXLE", "SINYAL", "WESEL", "COUNTER"]):
                    # --- JALANKAN SCRIPT LAMA (CEKLIS UTAMA) ---
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=300)
                        img = images[0]
                        width, height = img.size

                        if use_ocr:
                            # Logika Crop Script Lama
                            left, top, right, bottom = width*0.55, height*0.05, width*0.98, height*0.55
                            img_cropped = img.crop((left, top, right, bottom))
                            text_aset = pytesseract.image_to_string(img_cropped)

                            match_aset = re.findall(r'(?:WESEL|BLOK|SINYAL|COUNTER)\s+([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)', text_aset, re.IGNORECASE)
                            
                            if match_aset:
                                cleaned = [a.upper().replace(".", "").replace(" ", "") for a in match_aset]
                                for item in cleaned:
                                    if item not in assets: assets.append(item)
                                assets = assets[:5]

                            full_text = pytesseract.image_to_string(img).upper()
                            loc_pair = re.search(r'([A-Z]{3,4}\-[A-Z]{3,4})', full_text)
                            loc_single = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB)\b', full_text)

                            if loc_pair: found_short = loc_pair.group().upper()
                            elif loc_single: found_short = loc_single[0]
                            elif "BOGOR" in full_text: found_short = "BOO"
                    except:
                        continue
                    
                    # Failsafe script lama jika OCR kosong
                    if not assets:
                        assets = [p for p in name_only.split("_") if any(c.isdigit() for c in p)][:1]

                else:
                    # --- JALANKAN SCRIPT PDSE (JIKA BUKAN CEKLIS UTAMA) ---
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=150, last_page=10)
                        text_h1 = pytesseract.image_to_string(images[0]).upper()

                        if "PERALATAN DALAM PERSINYALAN ELEKTRIK" in text_h1:
                            assets = ["PDSE"] # Asset fix PDSE
                            
                            # Cari Halaman Foto Dokumentasi untuk Lokasi Utuh
                            target_page_text = ""
                            for img in images:
                                current_text = pytesseract.image_to_string(img).upper()
                                if "FOTO DOKUMENTASI" in current_text:
                                    target_page_text = current_text
                                    break
                            
                            if not target_page_text: target_page_text = text_h1

                            loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s]{3,20})', target_page_text)
                            if loc_match:
                                found_short = loc_match.group(1).strip().split('\n')[0]
                            else:
                                stations = ["BOGOR", "CILEBUT", "BOJONG GEDE", "CITAYAM", "DEPOK", "MANGGARAI"]
                                for s in stations:
                                    if s in target_page_text:
                                        found_short = s
                                        break
                    except:
                        continue

                # --- PENAMAAN AKHIR ---
                if assets:
                    for asset in assets:
                        new_name = f"PERAWATAN {asset} {found_short} {tgl}.pdf"
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