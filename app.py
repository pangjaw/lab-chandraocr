import streamlit as st
import json
import re
import os
import zipfile
import platform
import pytesseract
from io import BytesIO
from pdf2image import convert_from_bytes
from streamlit_lottie import st_lottie

# --- 1. KONFIGURASI ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def load_lottiefile(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except: return None

lottie_train = load_lottiefile("Metro Rail.json")

# --- 2. UI ---
st.set_page_config(page_title="Ganti Nama File Ceklis Sintelis", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS")

col1, col2 = st.columns([1, 1], gap="large")
with col1:
    st.subheader("📁 Input & Setting")
    use_ocr = st.checkbox("Gunakan OCR Otomatis", value=True)
    uploaded_files = st.file_uploader("Upload PDF", type="pdf", accept_multiple_files=True)

# --- 3. LOGIKA PROSES ---
if uploaded_files:
    zip_buffer = BytesIO()
    processed_files = []
    
    with col2:
        st.subheader("📋 Hasil Proses")
        placeholder = st.empty()
        with placeholder.container():
            if lottie_train: st_lottie(lottie_train, height=150, key="train_loader")
            st.info("🚂 Sedang memproses data Sintelis...")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for f in uploaded_files:
                name_only = os.path.splitext(f.name)[0].upper()
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                if not tgl_match: continue
                tgl = tgl_match.group()

                final_asset = ""
                final_loc = "LOKASI_TIDAK_TERDETEKSI"

                try:
                    images = convert_from_bytes(f.getvalue(), dpi=200, last_page=5)
                    text_h1 = pytesseract.image_to_string(images[0]).upper()
                    
                    # --- A. LOGIKA KHUSUS SERAT OPTIK ---
                    if "SERAT OPTIK" in name_only:
                        final_asset = "SERAT OPTIK"
                        otb_match = re.search(r'(OTB\s?FO|OTB)\s?(.+)', text_h1)
                        if otb_match:
                            final_loc = otb_match.group(0).split('\n')[0].strip()
                        else:
                            final_loc = "OTB_UNKNOWN"

                    # --- B. LOGIKA KHUSUS PTLS & PTDS ---
                    elif "TELEKOMUNIKASI" in name_only:
                        final_asset = "PTLS" if "LUAR STASIUN" in name_only else "PTDS"
                        loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s\-]{3,30})', text_h1)
                        if loc_match: final_loc = loc_match.group(1).strip().split('\n')[0]

                    # --- C. LOGIKA KHUSUS JPL ---
                    elif "PINTU PERLINTASAN" in name_only:
                        final_asset = "JPL"
                        jpl_num = re.search(r'JPL\s?(\d+)', text_h1)
                        jpl_loc = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s\-]{3,30})', text_h1)
                        num = jpl_num.group(1) if jpl_num else ""
                        loc = jpl_loc.group(1).strip().split('\n')[0] if jpl_loc else ""
                        final_loc = f"{num} {loc}".strip()

                    # --- D. LOGIKA CATU DAYA & CTC-CTS ---
                    elif any(x in name_only for x in ["CATU DAYA", "CTC-CTS"]):
                        final_asset = "CATU DAYA" if "CATU DAYA" in name_only else "CTC-CTS"
                        loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s\-]{3,30})', text_h1)
                        if loc_match: final_loc = loc_match.group(1).strip().split('\n')[0]

                    # --- E. LOGIKA UTAMA (WESEL, SINYAL, AXLE, POINT LOCK) ---
                    else:
                        is_point_lock = "POINT LOCK" in name_only
                        final_asset = "POINT LOCK" if is_point_lock else ""
                        
                        # OCR Crop untuk Aset (Wesel/Sinyal/Axle)
                        width, height = images[0].size
                        img_cropped = images[0].crop((width*0.55, height*0.05, width*0.98, height*0.55))
                        text_crop = pytesseract.image_to_string(img_cropped).upper()
                        
                        asset_match = re.findall(r'(?:WESEL|SINYAL|COUNTER|W)\s+([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)', text_crop)
                        if asset_match:
                            asset_code = asset_match[0].replace(".", "").replace(" ", "")
                            final_asset = f"POINT LOCK {asset_code}" if is_point_lock else asset_code
                        
                        # Lokasi Singkatan (BOO, CLT, dll)
                        loc_single = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB|BTT|CLT)\b', text_h1)
                        if loc_single: final_loc = loc_single[0]

                except: pass

                # Failsafe Nama
                if not final_asset: final_asset = "ASET"
                new_name = f"PERAWATAN {final_asset} {final_loc} {tgl}.pdf"
                zip_f.writestr(new_name, f.getvalue())
                processed_files.append(new_name)

        placeholder.empty()
        if processed_files:
            with st.container(height=300):
                for p_file in processed_files: st.write(f"✅ `{p_file}`")
            st.download_button("📥 DOWNLOAD HASIL (.ZIP)", zip_buffer.getvalue(), "Hasil_Sintelis_Update.zip", "application/zip", use_container_width=True, type="primary")

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis KAI Utility</div>", unsafe_allow_html=True)