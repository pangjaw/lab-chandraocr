import streamlit as st
import json
import re
import os
import zipfile
import platform
import pytesseract
import gc 
# Tambahkan library untuk manajemen gambar
from io import BytesIO
from pdf2image import convert_from_bytes
from streamlit_lottie import st_lottie
from PIL import ImageOps

# --- 1. UTILITY FUNCTIONS & CONFIG ---
if platform.system() == "Windows":
    # Sesuaikan path Tesseract jika berbeda di komputer lokalmu
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    # Untuk Streamlit Cloud (Linux)
    pytesseract.pytesseract.tesseract_cmd = 'tesseract'

def load_lottiefile(filepath: str):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except:
        return None

lottie_train = load_lottiefile("Metro Rail.json")

# --- 2. LOGIKA ADMIN MODE ---
# Mode admin aktif jika URL mengandung ?mode=admin
is_admin = st.query_params.get("mode") == "admin"

# --- 3. TAMPILAN UTAMA ---
st.set_page_config(page_title="Sintelis 1.21 BOO Utility", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS (OCR SCANNER)")

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
    
    # Bagian Admin Debug
    if is_admin:
        with st.expander("🛠️ Admin Debug Tools", expanded=False):
            st.info("Mode Admin: Fitur bantuan teknis aktif.")
            debug_mode = st.checkbox("Aktifkan Layar Intip & Trace Log (Debug Mode)", value=False)
    else:
        debug_mode = False

    # Tombol Hapus File
    if "file_uploader_key" not in st.session_state:
        st.session_state["file_uploader_key"] = 0

    if st.button("🗑️ Hapus Semua File", use_container_width=True):
        st.session_state["file_uploader_key"] += 1
        st.rerun()

    uploaded_files = st.file_uploader(
        "Upload PDF Hasil Scan", 
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
        
        # Animasi Lottie saat proses
        status_container = st.empty()
        with status_container.container():
            if lottie_train:
                st_lottie(lottie_train, height=150, key="train_loader")
            progress_text = st.empty()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
            for idx, f in enumerate(uploaded_files):
                progress_text.info(f"🚂 Memproses {idx+1}/{len(uploaded_files)} (OCR bekerja)...")
                
                # Ekstrak Tanggal dari Nama File Asli
                name_only = f.name.upper()
                tgl_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', name_only)
                
                if not tgl_match:
                    duplicate_errors.append(f"❌ `{f.name}`: Format tanggal (DD-MM-YYYY) tidak ditemukan.")
                    continue
                
                tgl_full = tgl_match.group(0)
                bln_angka = str(int(tgl_match.group(2)))
                thn_angka = tgl_match.group(3)
                prefix_periode = f"{thn_angka}-{bln_angka}"
                
                assets_found, target_keyword, kode_ceklis, kategori_nama = [], None, "", ""
                
                # Identifikasi Kategori Berdasarkan Nama File
                if any(x in name_only for x in ["WESEL", "WLSE"]): 
                    target_keyword, kode_ceklis, kategori_nama = "WESEL", "BPBYE1", "WESEL"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL", "ZP"]): 
                    target_keyword, kode_ceklis, kategori_nama = "AXLE", "BPBYE7", "AXC"
                elif any(x in name_only for x in ["SINYAL", "BLOK"]): 
                    target_keyword, kode_ceklis, kategori_nama = "SINYAL", "BPBYE3", "SINYAL"
                elif any(x in name_only for x in ["OPTIK", "OPTIC", "SERAT", "OTB"]): 
                    target_keyword, kode_ceklis, kategori_nama = "OPTIK", "BPBKF4", "" # Kosong agar OTB dari scan tidak double
                elif any(x in name_only for x in ["TELKOM", "LUAR", "PTLS"]): 
                    target_keyword, kode_ceklis, kategori_nama = "TELKOM_LUAR", "BPBKS16", "PTLS"

                if target_keyword:
                    try:
                        # 1. KONVERSI PDF KE GAMBAR (PAGE 1 SAJA)
                        images = convert_from_bytes(f.getvalue(), dpi=150, first_page=1, last_page=1)
                        img = images[0].convert('L') 
                        img = ImageOps.autocontrast(img) 
                        
                        # 2. CROP SETENGAH HALAMAN ATAS (OPTIMASI KECEPATAN)
                        width, height = img.size
                        img_cropped = img.crop((0, 0, width, int(height * 0.5)))
                        
                        if debug_mode: 
                            st.image(img_cropped, caption=f"Debug: Area Crop (50%) {f.name}")
                            
                        text_crop = pytesseract.image_to_string(img_cropped).upper()
                        lines = [line.strip() for line in text_crop.split('\n') if line.strip()]
                        
                        trace_logs = [] # CCTV Log Tracker

                        for line in lines:
                            # ==================== LOGIKA WESEL ====================
                            if target_keyword == "WESEL" and "WSL" in line and ":" in line:
                                trace_logs.append(f"🔍 [WESEL] Baris: '{line}'")
                                right_side = line.split(":")[-1].strip()
                                for n in ["WESEL ELEKTRIK TERLAYAN SETEMPAT", "WESEL ELEKTRIK", "PENGGERAK WESEL", "WESELPENGGERAK", "PENGGERAK", "ELEKTRIK", "WESEL"]:
                                    right_side = right_side.replace(n, "")
                                words = right_side.split()
                                if words:
                                    aid = words[0] if words[0].startswith("W") else f"W{words[0]}"
                                    loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    assets_found.append({"id": aid, "loc": loc_id})
                                    trace_logs.append(f"✅ OK: {aid} {loc_id}")

                            # ==================== LOGIKA AXLE COUNTER ====================
                            elif target_keyword == "AXLE" and "AXL" in line and ":" in line:
                                trace_logs.append(f"🔍 [AXC] Baris: '{line}'")
                                right_side = line.split(":")[-1].strip().replace("AXLE.COUNTER.", "").replace("AXLE COUNTER", "").replace(".", " ")
                                words = right_side.split()
                                if words:
                                    if words[0] == "ZP" and len(words) > 1:
                                        aid, loc_id = f"ZP {words[1]}", " ".join(words[2:])
                                    else:
                                        aid, loc_id = (words[0] if words[0].startswith("ZP") else f"ZP{words[0]}"), " ".join(words[1:])
                                    assets_found.append({"id": aid, "loc": loc_id.strip() or "LOKASI"})
                                    trace_logs.append(f"✅ OK: {aid} {loc_id}")

                            # ==================== LOGIKA SINYAL ====================
                            elif target_keyword == "SINYAL" and "SIN" in line and ":" in line:
                                trace_logs.append(f"🔍 [SINYAL] Baris: '{line}'")
                                right_side = line.split(":")[-1].strip()
                                for noise in ["SINYAL BLOK", "SINYAL MUKA", "SINYAL MASUK", "SINYAL KELUAR", "SINYAL LANGSIR", "SINYAL"]:
                                    right_side = right_side.replace(noise, "")
                                words = right_side.strip().split()
                                if words:
                                    aid, loc_id = words[0], " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    assets_found.append({"id": aid, "loc": loc_id})
                                    trace_logs.append(f"✅ OK: {aid} {loc_id}")

                            # ==================== LOGIKA SERAT OPTIK (OTB) ====================
                            elif target_keyword == "OPTIK" and "TRA" in line and ":" in line:
                                trace_logs.append(f"🔍 [OTB] Baris: '{line}'")
                                right_side = line.split(":")[-1].strip()
                                for noise in ["SERAT OPTIK", "KABEL OPTIK", "KABEL"]:
                                    right_side = right_side.replace(noise, "")
                                raw_otb = right_side.strip()
                                words = raw_otb.split()
                                if words:
                                    # Ambil OTB + ID (2 kata pertama)
                                    aid = " ".join(words[:2]) if len(words) > 1 else words[0]
                                    loc_id = " ".join(words[2:]) if len(words) > 2 else ""
                                    assets_found.append({"id": aid, "loc": loc_id})
                                    trace_logs.append(f"✅ OK: {aid} {loc_id}")

                            # ==================== LOGIKA TELKOM LUAR (PTLS) ====================
                            elif target_keyword == "TELKOM_LUAR" and "TRA" in line and ":" in line:
                                trace_logs.append(f"🔍 [PTLS] Baris: '{line}'")
                                right_side = line.split(":")[-1].strip()
                                for noise in ["TELEKOMUNIKASI", "TELKOM", "LUAR", "STASIUN", "PTLS", "RADIO", "BASE", "STATION"]:
                                    right_side = right_side.replace(noise, "")
                                words = right_side.strip().split()
                                if words:
                                    # ID Dihiraukan (Abaikan kata pertama), Ambil Sisa sebagai Lokasi
                                    loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    assets_found.append({"id": "", "loc": loc_id})
                                    trace_logs.append(f"✅ OK (ID Dihiraukan) -> LOC: {loc_id}")

                        if debug_mode and trace_logs:
                            with st.expander(f"🕵️ DETEKTIF LOG: {f.name}", expanded=True):
                                for log in trace_logs:
                                    if "✅" in log: st.success(log)
                                    else: st.text(log)

                        # Pembersihan Memory
                        del img, img_cropped, images
                        gc.collect() 
                    except Exception as e:
                        duplicate_errors.append(f"❌ `{f.name}`: OCR Error ({str(e)})")

                # --- 5. FINALISASI NAMA FILE ---
                if assets_found:
                    for asset in assets_found:
                        aid_clean = asset["id"].strip()
                        aloc_clean = asset["loc"].strip()
                        
                        # Gabungkan Kategori dan ID secara bersih (Menghindari spasi ganda)
                        part_nama = f"{kategori_nama} {aid_clean}".strip()
                        
                        if format_eksklusif:
                            new_name = f"{prefix_periode}_Resor 1.21 Boo_{kode_ceklis}_{jenis_kegiatan}_{part_nama}_{aloc_clean}_{tgl_full}.pdf"
                        else:
                            new_name = f"{jenis_kegiatan.upper()} {part_nama} {aloc_clean} {tgl_full}.pdf"
                        
                        # Pembersihan spasi berlebih menggunakan Regex
                        new_name = re.sub(r'\s+', ' ', new_name).strip()
                        new_name = new_name.replace("_ ", "_").replace(" _", "_")

                        if new_name not in unique_filenames:
                            zip_f.writestr(new_name, f.getvalue())
                            processed_files.append(new_name)
                            unique_filenames.add(new_name)
                        else:
                            duplicate_errors.append(f"⚠️ `{f.name}`: Duplikat pada ID `{aid_clean or aloc_clean}`")
                else:
                    if f.name not in [e.split("`")[1] for e in duplicate_errors if "`" in e]:
                        duplicate_errors.append(f"🔍 `{f.name}`: Gagal identifikasi ID Aset.")

        # Hapus Animasi saat selesai
        status_container.empty()

        # Tampilkan Tombol Download
        if processed_files:
            with btn_col:
                st.download_button(
                    label="📥 DOWNLOAD ZIP", 
                    data=zip_buffer.getvalue(), 
                    file_name="Hasil_Rename_Sintelis_BOO.zip", 
                    mime="application/zip", 
                    use_container_width=True, 
                    type="primary"
                )

        # Daftar Berhasil & Gagal
        with st.expander(f"✅ Berhasil Teridentifikasi ({len(processed_files)})", expanded=True):
            if processed_files:
                with st.container(height=150):
                    for p_file in processed_files: st.write(f"📄 `{p_file}`")
            else:
                st.write("Belum ada file.")

        with st.expander(f"❌ Gagal Diproses ({len(duplicate_errors)})", expanded=True):
            if duplicate_errors:
                with st.container(height=150):
                    for err in duplicate_errors: st.warning(err)
            else:
                st.write("Tidak ada kendala.")

# --- FOOTER ---
st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis 1.21 BOO Utility</div>", unsafe_allow_html=True)