import streamlit as st
import json
import re
import os
import zipfile
import platform
import pytesseract
import gc 
from io import BytesIO
from pdf2image import convert_from_bytes
from streamlit_lottie import st_lottie

# --- 1. KONFIGURASI TESSERACT ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def load_lottiefile(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return None

lottie_train = load_lottiefile("Metro Rail.json")

# --- 2. TAMPILAN UTAMA ---
st.set_page_config(page_title="Sintelis 1.21 BOO Utility", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📁 Input & Setting")
    use_ocr = st.checkbox("Gunakan OCR Otomatis", value=True)
    debug_mode = st.checkbox("Aktifkan Layar Intip (Debug Mode)", value=False)
    uploaded_files = st.file_uploader("Upload PDF", type="pdf", accept_multiple_files=True)

# --- 3. PROSES DATA ---
if uploaded_files:
    zip_buffer = BytesIO()
    processed_files = []
    unique_filenames = set() 
    
    with col2:
        st.subheader("📋 Hasil Proses")
        status_container = st.empty()
        
        with status_container.container():
            if lottie_train:
                st_lottie(lottie_train, height=150, key="train_loader")
            progress_text = st.empty()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for idx, f in enumerate(uploaded_files):
                progress_text.info(f"🚂 Sedang memproses ceklis ke-{idx+1} dari {len(uploaded_files)}...")
                
                name_only = f.name.upper()
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                if not tgl_match: continue
                
                tgl = tgl_match.group()
                assets = []
                found_short = "LOKASI"

                # Penentuan Target
                target_keyword = None
                if any(x in name_only for x in ["WESEL", "WLSE"]): target_keyword = "WESEL"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL"]): target_keyword = "AXLE"
                elif "SINYAL" in name_only: target_keyword = "SINYAL"

                # Logika PDSE (Tetap)
                if "PDSE" in name_only or "PERALATAN DALAM PERSINYALAN ELEKTRIK" in name_only:
                    assets = ["PDSE"]
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=100, last_page=5)
                        for img in images:
                            txt = pytesseract.image_to_string(img).upper()
                            if "FOTO DOKUMENTASI" in txt:
                                loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s]{3,15})', txt)
                                if loc_match: found_short = loc_match.group(1).strip().split('\n')[0]
                                break
                        del images
                    except: pass

                # Logika OCR (Hanya Kode Utama)
                elif target_keyword and use_ocr:
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=150, first_page=1, last_page=1)
                        img = images[0]
                        width, height = img.size
                        left, top, right, bottom = 0.0, height*0.07, width*1.0, height*0.20
                        img_cropped = img.crop((left, top, right, bottom))
                        
                        if debug_mode:
                            st.image(img_cropped, caption=f"Scan: {f.name}")
                            
                        text_crop = pytesseract.image_to_string(img_cropped).upper()
                        lines = [line.strip() for line in text_crop.split('\n') if line.strip()]
                        
                        noise_words = [
                            "PERAWATAN", "MINGGUAN", "BULANAN", "TAHUNAN", "CEKLIS",
                            "PENGGERAK", "WESEL", "ELEKTRIK", "TERLAYAN", "SETEMPAT", "TERPUSAT",
                            "AXLE", "COUNTER", "PERAGA", "SINYAL", "SAMPEL", "NOMOR", "INTERNAL"
                        ]

                        for line in lines:
                            if target_keyword in line or (target_keyword == "AXLE" and "COUNTER" in line):
                                # Deteksi Lokasi (Kata Terakhir)
                                parts_all = line.replace(".", " ").split()
                                if parts_all:
                                    found_short = parts_all[-1]

                                # Cari Kode Utama (Contoh: ZP12B atau W31A)
                                # Kita cari kata yang mengandung kombinasi huruf-angka atau yang bukan noise
                                clean_line = line.split(":")[-1].replace(".", " ") if ":" in line else line.replace(".", " ")
                                parts = clean_line.split()
                                
                                code_candidates = [w for w in parts if w not in noise_words and w != found_short]
                                
                                # Filter Tambahan: Buang kode internal yang mengandung 'AXL' di dalam teksnya
                                # agar tidak muncul 'AXL12200'
                                final_codes = [c for c in code_candidates if not c.startswith("AXL") or len(c) < 5]

                                if final_codes:
                                    # Ambil kode yang paling relevan (biasanya kata pertama atau kedua setelah filter)
                                    asset_code = final_codes[0]
                                    
                                    if len(asset_code) >= 2 and asset_code not in assets:
                                        assets.append(asset_code)
                        
                        del img, img_cropped, images
                        gc.collect() 
                    except: pass

                # Penamaan Final
                if assets:
                    for asset in assets:
                        loc_clean = found_short.replace(".", " ").strip()
                        new_name = f"PERAWATAN {asset} {loc_clean} {tgl}.pdf"
                        if new_name not in unique_filenames:
                            zip_f.writestr(new_name, f.getvalue())
                            processed_files.append(new_name)
                            unique_filenames.add(new_name)

        status_container.empty()

        if processed_files:
            st.success(f"✅ Berhasil memproses total **{len(processed_files)}** file.")
            with st.container(height=300):
                for p_file in processed_files:
                    st.write(f"📄 `{p_file}`")
            
            st.download_button(
                label=f"📥 DOWNLOAD {len(processed_files)} HASIL (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Hasil_Rename_Sintelis_BOO.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis 1.21 BOO Utility</div>", unsafe_allow_html=True)