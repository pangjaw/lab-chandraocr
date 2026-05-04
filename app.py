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

# --- 1. KONFIGURASI TESSERACT (Saran A) ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    # Untuk deployment di Streamlit Cloud (Linux)
    pytesseract.pytesseract.tesseract_cmd = 'tesseract'

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
    duplicate_errors = [] # (Saran D: Penampung error duplikat)
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
                progress_text.info(f"🚂 Memproses ceklis ke-{idx+1} dari {len(uploaded_files)}...")
                
                name_only = f.name.upper()
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                
                if not tgl_match:
                    duplicate_errors.append(f"⚠️ Skip: File `{f.name}` tidak memiliki format tanggal (DD-MM-YYYY).")
                    continue
                
                tgl = tgl_match.group()
                assets_found = []

                # Penentuan Target
                target_keyword = None
                if any(x in name_only for x in ["WESEL", "WLSE"]): target_keyword = "WESEL"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL"]): target_keyword = "AXLE"
                elif any(x in name_only for x in ["SINYAL", "BLOK", "ZP"]): target_keyword = "SINYAL"

                if target_keyword and use_ocr:
                    try:
                        # (Saran B: DPI 150 cukup, convert ke Grayscale 'L' untuk akurasi)
                        images = convert_from_bytes(f.getvalue(), dpi=150, first_page=1, last_page=1)
                        img = images[0].convert('L') 
                        
                        width, height = img.size
                        left, top, right, bottom = 0.0, height*0.05, width*1.0, height*0.25
                        img_cropped = img.crop((left, top, right, bottom))
                        
                        if debug_mode:
                            st.image(img_cropped, caption=f"Scan: {f.name}")
                            
                        text_crop = pytesseract.image_to_string(img_cropped).upper()
                        lines = [line.strip() for line in text_crop.split('\n') if line.strip()]
                        
                        noise_words = [
                            "PERAWATAN", "MINGGUAN", "BULANAN", "TAHUNAN", "CEKLIS", "ULANG",
                            "PENGGERAK", "WESEL", "ELEKTRIK", "AXLE", "COUNTER", "SIEMENS",
                            "PERAGA", "SINYAL", "SAMPEL", "NOMOR", "INTERNAL", "TERLAYAN", 
                            "SETEMPAT", "BLOK"
                        ]

                        for line in lines:
                            if any(k in line for k in ["SINYAL", "BLOK", "WESEL", "AXLE", "COUNTER"]):
                                clean_part = line.split(":")[-1].strip() if ":" in line else line.strip()
                                clean_part = clean_part.replace(".", " ")
                                words = clean_part.split()
                                
                                final_parts = [w for w in words if w not in noise_words]
                                
                                if final_parts:
                                    asset_no = final_parts[0]
                                    location_parts = final_parts[1:]
                                    
                                    if target_keyword == "WESEL" and not asset_no.startswith("W"):
                                        asset_no = f"W{asset_no}"
                                    elif ("AXLE" in name_only or "COUNTER" in name_only) and not asset_no.startswith("ZP"):
                                        asset_no = f"ZP{asset_no}"
                                    
                                    full_identity = asset_no
                                    if location_parts:
                                        full_identity += " " + " ".join(location_parts)
                                    
                                    if len(full_identity) >= 2 and full_identity not in assets_found:
                                        assets_found.append(full_identity)
                        
                        del img, img_cropped, images
                        gc.collect() 
                    except Exception as e:
                        # (Saran C: Error handling yang lebih informatif)
                        duplicate_errors.append(f"❌ OCR Error pada `{f.name}`: {str(e)}")

                # Penamaan Final & Logika Duplikat (Saran D)
                if assets_found:
                    for identity in assets_found:
                        new_name = f"PERAWATAN {identity} {tgl}.pdf"
                        if new_name not in unique_filenames:
                            zip_f.writestr(new_name, f.getvalue())
                            processed_files.append(new_name)
                            unique_filenames.add(new_name)
                        else:
                            duplicate_errors.append(f"⚠️ Gagal Rename: File `{f.name}` menghasilkan nama ganda `{new_name}`.")
                else:
                    # Jika gagal OCR atau keyword tidak cocok, tetap masukkan file asli
                    zip_f.writestr(f.name, f.getvalue())
                    processed_files.append(f.name)

        status_container.empty()

        # Menampilkan Hasil
        if processed_files:
            st.success(f"✅ Berhasil memproses **{len(processed_files)}** file.")
            with st.container(height=300):
                for p_file in processed_files:
                    st.write(f"📄 `{p_file}`")
            
            # Tampilkan list error/duplikat jika ada
            if duplicate_errors:
                with st.expander("📝 Log Peringatan & Kesalahan"):
                    for err in duplicate_errors:
                        st.warning(err)
            
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
