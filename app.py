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
    
    jenis_kegiatan = st.radio(
        "Pilih Jenis Kegiatan:",
        ["Perawatan", "Pemeriksaan"],
        index=0,
        horizontal=True
    )
    
    instansi = st.radio(
        "Pilih Instansi/Format Nama:",
        ["BTP JAK (Format Standar)", "BTP BD (Format Khusus Sintel Boo)"],
        index=0
    )
    
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
    processed_files, duplicate_errors, unique_filenames = [], [], set() 
    
    with col2:
        head_col, btn_col = st.columns([1.5, 1])
        with head_col:
            st.subheader("📋 Hasil Proses")
        
        status_container = st.empty()
        with status_container.container():
            if lottie_train:
                st_lottie(lottie_train, height=150, key="train_loader")
            progress_text = st.empty()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for idx, f in enumerate(uploaded_files):
                progress_text.info(f"🚂 Memproses {idx+1}/{len(uploaded_files)}...")
                
                name_only = f.name.upper()
                tgl_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', name_only)
                
                if not tgl_match:
                    duplicate_errors.append(f"❌ `{f.name}`: Format tanggal (DD-MM-YYYY) tidak ditemukan.")
                    continue
                
                tgl_full = tgl_match.group(0)
                bln_angka = str(int(tgl_match.group(2)))
                thn_angka = tgl_match.group(3)
                prefix_periode = f"{thn_angka}-{bln_angka}"
                
                assets_found, target_keyword, kode_ceklis = [], None, ""
                
                if any(x in name_only for x in ["WESEL", "WLSE"]): target_keyword, kode_ceklis = "WESEL", "BPBYE1"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL"]): target_keyword, kode_ceklis = "AXLE", "BPBYE7"
                elif any(x in name_only for x in ["SINYAL", "BLOK", "ZP"]): target_keyword, kode_ceklis = "SINYAL", "BPBYE3"

                if target_keyword:
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=150, first_page=1, last_page=1)
                        img = images[0].convert('L') 
                        width, height = img.size
                        img_cropped = img.crop((0.0, height*0.05, width*1.0, height*0.25))
                        
                        if debug_mode: st.image(img_cropped, caption=f"Scan: {f.name}")
                            
                        text_crop = pytesseract.image_to_string(img_cropped).upper()
                        lines = [line.strip() for line in text_crop.split('\n') if line.strip()]
                        
                        noise = ["PERAWATAN", "PEMERIKSAAN", "MINGGUAN", "BULANAN", "TAHUNAN", "CEKLIS", "ULANG", 
                                 "PENGGERAK", "WESEL", "ELEKTRIK", "AXLE", "COUNTER", "SIEMENS", "PERAGA", 
                                 "SINYAL", "SAMPEL", "NOMOR", "INTERNAL", "TERLAYAN", "SETEMPAT", "BLOK", 
                                 "MASUK", "KELUAR", "MUKA", "DAN", "LANGSIR", "JALAN"]

                        for line in lines:
                            if any(k in line for k in ["SINYAL", "BLOK", "WESEL", "AXLE", "COUNTER"]):
                                clean = line.split(":")[-1].strip() if ":" in line else line.strip()
                                words = clean.replace(".", " ").split()
                                final = [w for w in words if w not in noise]
                                
                                if final:
                                    aid, loc_id = final[0], " ".join(final[1:]) if len(final) > 1 else "LOKASI"
                                    if target_keyword == "WESEL" and not aid.startswith("W"): aid = f"W{aid}"
                                    elif target_keyword == "AXLE" and not aid.startswith("ZP"): aid = f"ZP{aid}"
                                    assets_found.append({"id": aid, "loc": loc_id})
                        
                        del img, img_cropped, images
                        gc.collect() 
                    except Exception as e:
                        duplicate_errors.append(f"❌ `{f.name}`: OCR Error ({str(e)})")

                if assets_found:
                    for asset in assets_found:
                        aid, aloc = asset["id"], asset["loc"]
                        kegiatan_label = jenis_kegiatan.upper()
                        
                        if format_eksklusif:
                            new_name = f"{prefix_periode}_Resor 1.21 Boo_{kode_ceklis}_{jenis_kegiatan}_{aid}_{aloc}_{tgl_full}.pdf"
                        else:
                            new_name = f"{kegiatan_label} {aid} {aloc} {tgl_full}.pdf"

                        if new_name not in unique_filenames:
                            zip_f.writestr(new_name, f.getvalue())
                            processed_files.append(new_name)
                            unique_filenames.add(new_name)
                        else:
                            duplicate_errors.append(f"⚠️ `{f.name}`: ID `{aid}` duplikat.")
                else:
                    duplicate_errors.append(f"🔍 `{f.name}`: Gagal identifikasi ID Aset.")

        status_container.empty()

        if processed_files:
            with btn_col:
                st.download_button(label="📥 DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name="Hasil_Rename_Sintelis_BOO.zip", mime="application/zip", use_container_width=True, type="primary")

        # Expander Sukses (dengan internal scroll)
        with st.expander(f"✅ Sukses Teridentifikasi ({len(processed_files)})", expanded=True):
            if processed_files:
                with st.container(height=300):
                    for p_file in processed_files: st.write(f"📄 `{p_file}`")
            else:
                st.write("Belum ada file yang berhasil diproses.")

        # Expander Gagal (dengan internal scroll)
        with st.expander(f"❌ Gagal Diproses ({len(duplicate_errors)})", expanded=True):
            if duplicate_errors:
                with st.container(height=300):
                    for err in duplicate_errors: st.warning(err)
            else:
                st.write("Tidak ada kendala pada file.")

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis 1.21 BOO Utility</div>", unsafe_allow_html=True)
