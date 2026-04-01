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
    except: return None

lottie_train = load_lottiefile("Metro Rail.json")

# --- 2. ANTARMUKA UTAMA (UI) ---
st.set_page_config(page_title="Ganti Nama File Ceklis Sintelis", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📁 Input & Setting")
    st.info("Script ini bekerja berdasarkan Syarat Mutlak Jalur A, B, C, dan D.")
    uploaded_files = st.file_uploader("Upload file PDF Ceklis", type="pdf", accept_multiple_files=True)

# --- 3. PROSES DATA BERDASARKAN SYARAT MUTLAK ---
if uploaded_files:
    zip_buffer = BytesIO()
    processed_files = []
    
    with col2:
        st.subheader("📋 Hasil Proses")
        placeholder = st.empty()
        with placeholder.container():
            if lottie_train: st_lottie(lottie_train, height=150, key="train_loader")
            st.info("🚂 Menjalankan Logika Deteksi Jalur...")

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for f in uploaded_files:
                name_only = os.path.splitext(f.name)[0].upper()
                
                # SYARAT MUTLAK 1: Deteksi Tanggal dari Nama File Asli
                tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
                if not tgl_match: continue
                tgl = tgl_match.group()

                final_asset = ""
                final_loc = "LOKASI_TIDAK_TERDETEKSI"

                try:
                    # Ambil halaman pertama dengan DPI 200 untuk akurasi
                    images = convert_from_bytes(f.getvalue(), dpi=200, first_page=1, last_page=1)
                    img_first = images[0]
                    text_full = pytesseract.image_to_string(img_first).upper()
                    
                    # --- JALUR A: PDSE / CATU DAYA / CTC-CTS (Lokasi Utuh) ---
                    if any(x in name_only for x in ["PERSINYALAN ELEKTRIK", "CATU DAYA", "CTC-CTS"]):
                        if "PERSINYALAN ELEKTRIK" in name_only: final_asset = "PDSE"
                        elif "CATU DAYA" in name_only: final_asset = "CATU DAYA"
                        else: final_asset = "CTC-CTS"
                        
                        # Syarat Mutlak: Hanya ambil teks tepat setelah label LOKASI
                        loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s\-]{3,20})', text_full)
                        if loc_match:
                            final_loc = loc_match.group(1).strip().split('\n')[0]

                    # --- JALUR B: TELEKOMUNIKASI (PTLS/PTDS) & JPL ---
                    elif any(x in name_only for x in ["TELEKOMUNIKASI", "PINTU PERLINTASAN"]):
                        if "LUAR STASIUN" in name_only: final_asset = "PTLS"
                        elif "DI STASIUN" in name_only: final_asset = "PTDS"
                        elif "PINTU PERLINTASAN" in name_only: final_asset = "JPL"
                        
                        loc_match = re.search(r'(?:LOKASI|STASIUN)\s*[:\-]?\s*([A-Z\s\-]{3,30})', text_full)
                        loc_raw = loc_match.group(1).strip().split('\n')[0] if loc_match else ""
                        
                        if final_asset == "JPL":
                            # Syarat Mutlak: Ambil nomor JPL dari teks dokumen
                            jpl_num = re.search(r'JPL\s?(?:NO\.?\s?)?(\d+)', text_full)
                            num = jpl_num.group(1) if jpl_num else ""
                            final_loc = f"{num} {loc_raw}".strip()
                        else:
                            final_loc = loc_raw

                    # --- JALUR C: SERAT OPTIK (Detail OTB) ---
                    elif "SERAT OPTIK" in name_only:
                        final_asset = "SERAT OPTIK"
                        # Syarat Mutlak: Ambil string setelah kata OTB FO atau OTB
                        otb_match = re.search(r'(OTB\s?FO|OTB)\s?([^\n]+)', text_full)
                        if otb_match: 
                            final_loc = otb_match.group(0).strip()

                    # --- JALUR D: UNIT LUAR (Wesel, Sinyal, Point Lock - OCR CROP) ---
                    else:
                        is_point_lock = "POINT LOCK" in name_only
                        
                        # Syarat Mutlak: CROP AREA KANAN ATAS (Koordinat Aset)
                        w, h = img_first.size
                        img_crop = img_first.crop((w*0.55, h*0.02, w*0.98, h*0.45))
                        text_crop = pytesseract.image_to_string(img_crop).upper()
                        
                        # Cari Kode Aset (W, WSL, ZP, AXC, B, J, M)
                        code_match = re.search(r'\b(W\d+[A-Z]?|WSL\d+|ZP\d+|AXC\d+|B\d+|M\d+|SINYAL\s?[A-Z\d]+)\b', text_crop)
                        
                        if code_match:
                            asset_code = code_match.group(1).replace("WSL", "W")
                        else:
                            # Failsafe: Jika crop gagal, cari pola kode di nama file asli
                            fallback = re.search(r'(W\d+|ZP\d+|AXC\d+|B\d+|M\d+)', name_only)
                            asset_code = fallback.group() if fallback else "ASET"

                        final_asset = f"POINT LOCK {asset_code}" if is_point_lock else asset_code
                        
                        # Ambil Singkatan Lokasi (3 Huruf)
                        loc_short = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB|BTT|CLT)\b', text_full)
                        final_loc = loc_short[0] if loc_short else "LOKASI"

                except:
                    final_asset = "ASET"
                    final_loc = "LOKASI"

                # PEMBENTUKAN NAMA FINAL
                new_name = f"PERAWATAN {final_asset} {final_loc} {tgl}.pdf"
                # Bersihkan karakter terlarang Windows
                new_name = re.sub(r'[\\/*?:"<>|]', "", new_name)
                
                zip_f.writestr(new_name, f.getvalue())
                processed_files.append(new_name)

        placeholder.empty()
        if processed_files:
            with st.container(height=300):
                for p_file in processed_files: st.write(f"✅ `{p_file}`")
            st.download_button("📥 DOWNLOAD HASIL (.ZIP)", zip_buffer.getvalue(), "Hasil_Sintelis_Update.zip", "application/zip", use_container_width=True, type="primary")

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis KAI Utility v2.1</div>", unsafe_allow_html=True)