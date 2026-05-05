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
else:
    pytesseract.pytesseract.tesseract_cmd = 'tesseract'

def load_lottiefile(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return None

lottie_train = load_lottiefile("Metro Rail.json")

# --- 2. LOGIKA ADMIN MODE ---
is_admin = st.query_params.get("mode") == "admin"

# --- 3. TAMPILAN UTAMA ---
st.set_page_config(page_title="Sintelis 1.21 BOO Utility", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS")

col1, col2 = st.columns([1, 1], gap="large")

with col1:
    st.subheader("📁 Input & Setting")
    
    # PILIHAN INSTANSI (Menentukan Format Nama)
    instansi = st.radio(
        "Pilih Instansi/Format Nama:",
        ["BTP JAK (Format Standar)", "BTP BD (Format Eksklusif Resor)"],
        index=0,
        help="BTP JAK menggunakan format lama. BTP BD menggunakan format baru (2026-1_...)"
    )
    
    # Set flag format berdasarkan pilihan
    format_eksklusif = True if "BTP BD" in instansi else False
    
    if is_admin:
        with st.expander("🛠️ Admin Debug Tools", expanded=False):
            st.info("Mode Admin: Fitur bantuan teknis.")
            debug_mode = st.checkbox("Aktifkan Layar Intip (Debug Mode)", value=False)
    else:
        debug_mode = False

    if "file_uploader_key" not in st.session_state:
        st.session_state["file_uploader_key"] = 0

    if st.button("🗑️ Hapus Semua File", use_container_width=True):
        st.session_state["file_uploader_key"] += 1
        st.rerun()

    uploaded_files = st.file_uploader(
        "Upload PDF", 
        type="pdf", 
        accept_multiple_files=True, 
        key=f"uploader_{st.session_state['file_uploader_key']}"
    )

# --- 4. PROSES DATA ---
if uploaded_files:
    zip_buffer = BytesIO()
    processed_files = []
    duplicate_errors = [] 
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
                    duplicate_errors.append(f"⚠️ Skip: File `{f.name}` tidak memiliki format tanggal (DD-MM-YYYY) di nama file aslinya.")
                    continue
                
                tgl = tgl_match.group()
                assets_found = []

                target_keyword = None
                kode_ceklis = ""
                
                if any(x in name_only for x in ["WESEL", "WLSE"]): 
                    target_keyword = "WESEL"
                    kode_ceklis = "BPBYE1"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL"]): 
                    target_keyword = "AXLE"
                    kode_ceklis = "BPBYE7"
                elif any(x in name_only for x in ["SINYAL", "BLOK", "ZP"]): 
                    target_keyword = "SINYAL"
                    kode_ceklis = "BPBYE3"

                # OCR Sekarang Selalu Aktif secara default
                if target_keyword:
                    try:
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
                            "SETEMPAT", "BLOK", "MASUK", "KELUAR", "MUKA", "ULANG",
                            "DAN", "LANGSIR", "JALAN"
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
                                    
                                    loc_id = " ".join(location_parts) if location_parts else "LOKASI"
                                    assets_found.append({"id": asset_no, "loc": loc_id})
                        
                        del img, img_cropped, images
                        gc.collect() 
                    except Exception as e:
                        duplicate_errors.append(f"❌ OCR Error pada `{f.name}`: {str(e)}")

                if assets_found:
                    for asset_data in assets_found:
                        aid = asset_data["id"]
                        aloc = asset_data["loc"]
                        
                        # Logika Penamaan berdasarkan pilihan Tombol BTP JAK/BD
                        if format_eksklusif:
                            new_name = f"2026-1_Resor 1.21 Boo_{kode_ceklis}_Perawatan_{aid}_{aloc}_{tgl}.pdf"
                        else:
                            new_name = f"PERAWATAN {aid} {aloc} {tgl}.pdf"

                        if new_name not in unique_filenames:
                            zip_f.writestr(new_name, f.getvalue())
                            processed_files.append(new_name)
                            unique_filenames.add(new_name)
                        else:
                            duplicate_errors.append(f"⚠️ Gagal Rename: ID `{aid}` sudah ada.")
                else:
                    zip_f.writestr(f.name, f.getvalue())
                    processed_files.append(f"{f.name} (Gagal Identifikasi)")

        status_container.empty()

        if processed_files:
            st.success(f"✅ Berhasil memproses **{len(processed_files)}** file.")
            with st.container(height=300):
                for p_file in processed_files:
                    st.write(f"📄 `{p_file}`")
            
            if duplicate_errors:
                st.subheader("📝 Log Peringatan & Kesalahan")
                with st.container(height=250, border=True):
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
