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
    
    jenis_kegiatan = st.radio("Pilih Jenis Kegiatan:", ["Perawatan", "Pemeriksaan"], index=0, horizontal=True)
    instansi = st.radio("Pilih Instansi/Format Nama:", ["BTP JAK (Format Standar)", "BTP BD (Format Khusus Sintel Boo)"], index=0)
    format_eksklusif = True if "BTP BD" in instansi else False
    
    if is_admin:
        with st.expander("🛠️ Admin Debug Tools", expanded=False):
            debug_mode = st.checkbox("Aktifkan Layar Intip (Debug Mode)", value=False)
    else:
        debug_mode = False

    if "file_uploader_key" not in st.session_state:
        st.session_state["file_uploader_key"] = 0

    if st.button("🗑️ Hapus Semua File", use_container_width=True):
        st.session_state["file_uploader_key"] += 1
        st.rerun()

    uploaded_files = st.file_uploader("Upload PDF", type="pdf", accept_multiple_files=True, key=f"uploader_{st.session_state['file_uploader_key']}")

# --- 4. PROSES DATA ---
if uploaded_files:
    zip_buffer = BytesIO()
    processed_files, duplicate_errors, used_names_count = [], [], {} 
    
    with col2:
        head_col, btn_col = st.columns([1.5, 1])
        with head_col: st.subheader("📋 Hasil Proses")
        
        status_container = st.empty()
        with status_container.container():
            if lottie_train: st_lottie(lottie_train, height=150, key="train_loader")
            progress_text = st.empty()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for idx, f in enumerate(uploaded_files):
                progress_text.info(f"Memproses {idx+1}/{len(uploaded_files)}...")
                
                name_orig = f.name.upper()
                tgl_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', name_orig)
                if not tgl_match:
                    duplicate_errors.append(f"❌ `{f.name}`: Format tanggal (DD-MM-YYYY) tidak ditemukan.")
                    continue
                
                tgl_full = tgl_match.group(0)
                bln_angka = str(int(tgl_match.group(2)))
                prefix_periode = f"{tgl_match.group(3)}-{bln_angka}"
                
                assets_found, target_keyword, kode_ceklis = [], None, ""
                
                # --- JALUR IDENTIFIKASI (KEMBALI KE FORMAT ASLI) ---
                if any(x in name_orig for x in ["WESEL", "WLSE"]): 
                    target_keyword, kode_ceklis = "WESEL", "BPBYE1"
                elif any(x in name_orig for x in ["AXLE", "COUNTER", "AXL"]): 
                    target_keyword, kode_ceklis = "AXLE", "BPBYE7"
                elif any(x in name_orig for x in ["SINYAL", "BLOK", "ZP"]): 
                    target_keyword, kode_ceklis = "SINYAL", "BPBYE3"
                elif any(x in name_orig for x in ["SERAT OPTIK", "OTB"]): 
                    target_keyword, kode_ceklis = "OTB", "BPBKF4"

                if target_keyword:
                    try:
                        images = convert_from_bytes(f.getvalue(), dpi=150, first_page=1, last_page=1)
                        img = images[0].convert('L')
                        
                        # Area Crop Dinamis
                        is_otb_stasiun = (target_keyword == "OTB" and "JPL" not in name_orig)
                        crop_h = 0.50 if is_otb_stasiun else 0.25
                        
                        img_cropped = img.crop((0.0, img.size[1]*0.03, img.size[0]*1.0, img.size[1]*crop_h))
                        if debug_mode: st.image(img_cropped, caption=f"Scan: {f.name}")
                        
                        text_crop = pytesseract.image_to_string(img_cropped).upper()
                        lines = [line.strip() for line in text_crop.split('\n') if line.strip()]

                        # --- LOGIKA EKSTRAKSI PER ITEM ---
                        for line in lines:
                            if target_keyword == "OTB":
                                # Perbaikan OTB: Menggunakan Regex agar tidak gagal karena karakter sampah (:) atau (TRA)
                                otb_match = re.search(r'OTB\s+(?:FO\s+)?([A-Z0-9\s]+?)\s+(.*)', line)
                                if otb_match:
                                    aid = f"OTB {otb_match.group(1).strip()}"
                                    loc_id = otb_match.group(2).strip()
                                    assets_found.append({"id": aid, "loc": loc_id})
                                    
                            elif target_keyword == "WESEL":
                                if "WESEL" in line or ":" in line:
                                    clean = line.split(":")[-1].strip() if ":" in line else line.replace("WESEL", "").strip()
                                    words = clean.split()
                                    if words:
                                        id_w = words[0] if words[0].startswith("W") else f"W{words[0]}"
                                        loc_w = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                        assets_found.append({"id": id_w, "loc": loc_w})

                            elif target_keyword == "SINYAL":
                                if "SINYAL" in line or ":" in line:
                                    clean = line.split(":")[-1].strip() if ":" in line else line.replace("SINYAL", "").strip()
                                    words = clean.split()
                                    if words:
                                        assets_found.append({"id": words[0], "loc": " ".join(words[1:]) if len(words) > 1 else "LOKASI"})

                            elif target_keyword == "AXLE":
                                if any(x in line for x in ["AXLE", "COUNTER", "ZP"]):
                                    clean = line.split(":")[-1].strip() if ":" in line else line.strip()
                                    words = clean.split()
                                    if words:
                                        id_ax = words[0] if words[0].startswith("ZP") else f"ZP{words[0]}"
                                        assets_found.append({"id": id_ax, "loc": " ".join(words[1:]) if len(words) > 1 else "LOKASI"})

                        del img, images; gc.collect()
                    except Exception as e:
                        duplicate_errors.append(f"❌ `{f.name}`: OCR Error ({str(e)})")

                # --- JALUR FILENAME SCAN (PTDS, PTLS, DLL) ---
                else:
                    if "PTDS" in name_orig: target_keyword, kode_ceklis = "PTDS", "BPBKS15"
                    elif "PTLS" in name_orig: target_keyword, kode_ceklis = "PTLS", "BPBKS16"
                    elif "PTPP" in name_orig: target_keyword, kode_ceklis = "PTPP", "BPBKS17"
                    elif any(x in name_orig for x in ["WAYSTATION", "WS"]): target_keyword, kode_ceklis = "RADIO WAYSTATION", "BPBKS4"
                    elif "BASESTATION" in name_orig: target_keyword, kode_ceklis = "RADIO BASESTATION", "BPBKF1"

                    if target_keyword:
                        parts = name_orig.split(target_keyword)
                        loc_part = parts[-1].split(tgl_full)[0].strip("_ ") if len(parts) > 1 else "LOKASI"
                        assets_found.append({"id": target_keyword, "loc": loc_part})

                # --- PENYUSUNAN FILE ---
                if assets_found:
                    for asset in assets_found:
                        aid, aloc = asset["id"], asset["loc"]
                        if format_eksklusif:
                            base = f"{prefix_periode}_Resor 1.21 Boo_{kode_ceklis}_{jenis_kegiatan}_{aid}_{aloc}_{tgl_full}"
                        else:
                            base = f"{jenis_kegiatan.upper()} {aid} {aloc} {tgl_full}"
                        
                        if base in used_names_count:
                            used_names_count[base] += 1
                            final_name = f"{base} ({used_names_count[base]}).pdf"
                        else:
                            used_names_count[base] = 0
                            final_name = f"{base}.pdf"

                        zip_f.writestr(final_name, f.getvalue())
                        processed_files.append(final_name)
                else:
                    duplicate_errors.append(f"🔍 `{f.name}`: Gagal identifikasi aset.")

        status_container.empty()
        if processed_files:
            with btn_col: 
                st.download_button(label="📥 DOWNLOAD ZIP", data=zip_buffer.getvalue(), 
                                 file_name="Hasil_Rename_Sintelis_BOO.zip", mime="application/zip", 
                                 use_container_width=True, type="primary")

        with st.expander(f"✅ Berhasil ({len(processed_files)})", expanded=True):
            for p_file in processed_files: st.write(f"📄 `{p_file}`")

        if duplicate_errors:
            with st.expander(f"❌ Gagal ({len(duplicate_errors)})", expanded=True):
                for err in duplicate_errors: st.warning(err)

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis 1.21 BOO Utility</div>", unsafe_allow_html=True)
