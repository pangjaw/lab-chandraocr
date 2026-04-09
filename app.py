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
st.set_page_config(page_title="Ganti Nama File Ceklis Sintelis", page_icon="📑", layout="wide")
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
    # Menggunakan set untuk mencegah duplikat nama file secara keseluruhan
    unique_filenames = set()
    
    with col2:
        st.subheader("📋 Hasil Proses")
        placeholder = st.empty()
        
        with placeholder.container():
            if lottie_train:
                st_lottie(lottie_train, height=150, key="train_loader")
            st.info("🚂 Sedang memproses ceklis...")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for f in uploaded_files:
                name_only = f.name.upper()
                
                # Cari Tanggal (Format: DD-MM-YYYY)
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                if not tgl_match: 
                    st.warning(f"⚠️ Tanggal tidak ditemukan di nama file: {f.name}")
                    continue
                
                tgl = tgl_match.group()
                assets = []
                found_short = "LOKASI_TIDAK_TERDETEKSI"

                # --- PENENTUAN TARGET KEYWORD ---
                target_keyword = None
                if any(x in name_only for x in ["WESEL", "WLSE"]):
                    target_keyword = "WESEL"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL"]):
                    target_keyword = "AXLE"
                elif "SINYAL" in name_only:
                    target_keyword = "SINYAL"

                # --- LOGIKA 1: KHUSUS PDSE ---
                if "PDSE" in name_only or "PERALATAN DALAM PERSINYALAN ELEKTRIK" in name_only:
                    assets = ["PDSE"]
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=150, last_page=10)
                        target_page_text = ""
                        for img in images:
                            txt = pytesseract.image_to_string(img).upper()
                            if "FOTO DOKUMENTASI" in txt:
                                target_page_text = txt.split("FOTO DOKUMENTASI")[-1]
                                break
                        loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s]{3,20})', target_page_text)
                        if loc_match:
                            found_short = loc_match.group(1).strip().split('\n')[0]
                    except:
                        pass

                # --- LOGIKA 2: OCR BERDASARKAN TARGET ---
                elif target_keyword:
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=200, first_page=1, last_page=1)
                        img = images[0]
                        width, height = img.size

                        if use_ocr:
                            left, top, right, bottom = 0.0, height*0.07, width*1.0, height*0.20
                            img_cropped = img.crop((left, top, right, bottom))
                            
                            if debug_mode:
                                st.image(img_cropped, caption=f"Area Scan Fokus Aset ({target_keyword})")
                                
                            text_crop = pytesseract.image_to_string(img_cropped).upper()
                            lines = [line.strip() for line in text_crop.split('\n') if line.strip()]
                            
                            noise_words = ["PERAWATAN", "MINGGUAN", "BULANAN", "TAHUNAN", "CEKLIS"]

                            for line in lines:
                                if target_keyword in line or (target_keyword == "AXLE" and "COUNTER" in line):
                                    clean_line = line.split(":")[-1].strip() if ":" in line else line.strip()
                                    clean_line = clean_line.replace(".", " ")
                                    
                                    parts = clean_line.split()
                                    if len(parts) >= 2:
                                        found_short = parts[-1] 
                                        asset_parts = [w for w in parts[:-1] if w not in noise_words]
                                        asset_full_name = " ".join(asset_parts) 
                                        asset_full_name = " ".join(asset_full_name.split())
                                        
                                        if asset_full_name and asset_full_name not in assets:
                                            if len(asset_full_name) > 3:
                                                assets.append(asset_full_name)
                            
                            assets = assets[:5]
                    except Exception as e:
                        st.error(f"Error pada {f.name}: {e}")

                # --- 4. PENAMAAN FINAL & ANTI DUPLIKAT ---
                if assets:
                    for asset in assets:
                        loc_clean = found_short.replace(".", " ").strip()
                        new_name = f"PERAWATAN {asset} {loc_clean} {tgl}.pdf"
                        
                        # Cek apakah nama file sudah pernah dibuat sebelumnya
                        if new_name not in unique_filenames:
                            zip_f.writestr(new_name, f.getvalue())
                            processed_files.append(new_name)
                            unique_filenames.add(new_name)
                else:
                    st.error(f"❌ Tidak ada aset {target_keyword if target_keyword else ''} terdeteksi di: {f.name}")

        placeholder.empty()

        if processed_files:
            # Tampilkan Total File
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