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
    uploaded_files = st.file_uploader("Upload PDF Ceklis", type="pdf", accept_multiple_files=True)

# --- 3. PROSES DATA BERDASARKAN SYARAT MUTLAK ---
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
                
                # SYARAT MUTLAK: Deteksi Tanggal dari Nama File Asli
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                if not tgl_match: continue
                tgl = tgl_match.group()

                assets = []
                found_short = "LOKASI"

                try:
                    # Ambil halaman pertama untuk scanning
                    images = convert_from_bytes(f.getvalue(), dpi=200, first_page=1, last_page=1)
                    img_first = images[0]
                    text_full = pytesseract.image_to_string(img_first).upper()

                    # --- LOGIKA 1: CEKLIS PDSE (LOKASI UTUH) ---
                    if "PERALATAN DALAM PERSINYALAN ELEKTRIK" in name_only:
                        assets = ["PDSE"]
                        # Ambil teks tepat setelah label LOKASI sampai baris baru
                        loc_match = re.search(r'LOKASI\s*[:\-]?\s*([A-Z]+)', text_full)
                        if loc_match:
                            found_short = loc_match.group(1).strip()

                    # --- LOGIKA 2: CEKLIS JPL (PINTU PERLINTASAN) ---
                    elif "PINTU PERLINTASAN" in name_only:
                        assets = ["JPL"]
                        # Ekstraksi Nomor JPL (Contoh: JPL 27)
                        jpl_num = re.search(r'JPL\s?(?:NO\.?\s?)?(\d+)', text_full)
                        num = jpl_num.group(1) if jpl_num else ""
                        
                        # Ekstraksi Rute (Contoh: BOO-CLT)
                        route = re.search(r'\b([A-Z]{3,4}\-[A-Z]{3,4})\b', text_full)
                        if route:
                            found_short = f"{num} {route.group(1)}"
                        else:
                            loc_match = re.search(r'LOKASI\s*[:\-]?\s*([A-Z]+)', text_full)
                            loc_raw = loc_match.group(1).strip() if loc_match else "LOKASI"
                            found_short = f"{num} {loc_raw}".strip()

                    # --- LOGIKA 3: CEKLIS UNIT LUAR (AXLE, SINYAL, WESEL) ---
                    elif any(x in name_only for x in ["AXLE", "SINYAL", "WESEL", "COUNTER", "POINT LOCK"]):
                        # CROP AREA KANAN ATAS (Koordinat Aset)
                        w, h = img_first.size
                        img_crop = img_first.crop((w*0.55, h*0.02, w*0.98, h*0.45))
                        text_crop = pytesseract.image_to_string(img_crop).upper()
                        
                        # Regex Kode Aset (W81, ZP112, dll)
                        code_match = re.search(r'\b(W\d+|ZP\d+|AXC\d+|B\d+|[A-Z]\d+)\b', text_crop)
                        asset_code = code_match.group(1) if code_match else "ASET"
                        
                        if "POINT LOCK" in name_only:
                            assets = [f"POINT LOCK {asset_code}"]
                        elif "SINYAL" in name_only:
                            assets = [f"SINYAL {asset_code}"]
                        else:
                            assets = [asset_code]
                        
                        # Singkatan Lokasi 3 Huruf
                        loc_list = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB|BTT|CLT)\b', text_full)
                        found_short = loc_list[0] if loc_list else "LOKASI"

                except:
                    assets = ["ASET"]
                    found_short = "LOKASI"

                # --- PENAMAAN FINAL ---
                for asset in assets:
                    new_name = f"PERAWATAN {asset} {found_short} {tgl}.pdf"
                    # Bersihkan karakter terlarang Windows
                    new_name = re.sub(r'[\\/*?:"<>|]', "", new_name)
                    zip_f.writestr(new_name, f.getvalue())
                    processed_files.append(new_name)

        placeholder.empty()

        if processed_files:
            with st.container(height=300):
                for p_file in processed_files:
                    st.write(f"✅ `{p_file}`")
            
            st.download_button(
                label="📥 DOWNLOAD SEMUA HASIL (.ZIP)",
                data=zip_buffer.getvalue(),
                file_name="Hasil_Rename_Sintelis_Update.zip",
                mime="application/zip",
                use_container_width=True,
                type="primary"
            )

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis KAI Utility v2.3</div>", unsafe_allow_html=True)