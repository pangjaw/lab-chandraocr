import streamlit as st
import json
import re
import os
import zipfile
import platform
import pytesseract
import gc 
# Library manajemen gambar dan PDF
from io import BytesIO
from pdf2image import convert_from_bytes
from streamlit_lottie import st_lottie
from PIL import ImageOps

# --- 1. UTILITY FUNCTIONS & CONFIG ---
# Konfigurasi Tesseract berdasarkan sistem operasi
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

# Flag session untuk mengunci proses agar tidak rerun saat download
if "download_done" not in st.session_state:
    st.session_state.download_done = False

# --- 2. LOGIKA ADMIN MODE ---
# Mengaktifkan fitur tambahan jika mode admin dipicu melalui URL (?mode=admin)
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
    
    # Bagian Admin Debugging untuk memantau hasil scan mentah
    if is_admin:
        with st.expander("🛠️ Admin Debug Tools", expanded=False):
            st.info("Mode Admin Aktif: Gunakan fitur ini untuk melihat hasil OCR mentah.")
            debug_mode = st.checkbox("Aktifkan Layar Intip & Trace Log (Debug Mode)", value=False)
    else:
        debug_mode = False

    # Inisialisasi Key untuk File Uploader agar bisa di-reset
    if "file_uploader_key" not in st.session_state:
        st.session_state["file_uploader_key"] = 0

    if st.button("🗑️ Hapus Semua File", use_container_width=True):
        st.session_state["file_uploader_key"] += 1
        st.session_state.download_done = False
        st.rerun()

    uploaded_files = st.file_uploader(
        "Upload PDF Hasil Scan", 
        type="pdf", 
        accept_multiple_files=True, 
        key=f"uploader_{st.session_state['file_uploader_key']}"
    )

# --- 4. PROSES DATA ---
with col2:
    if uploaded_files:
        # LOGIC GATE: Hanya jalankan OCR jika status download_done masih False
        if not st.session_state.download_done:
            # Persiapan variabel pemrosesan di dalam memori (Zero Storage)
            zip_buffer = BytesIO()
            processed_files, duplicate_errors, unique_filenames = [], [], set() 
            
            # Area Animasi Kereta & Progress Bar
            status_container = st.empty()
            with status_container.container():
                if lottie_train:
                    st_lottie(lottie_train, height=150, key="train_loader")
                progress_text = st.empty()

            # Mulai Membuka ZIP di dalam Memori
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
                for idx, f in enumerate(uploaded_files):
                    progress_text.info(f"🚂 Memproses {idx+1}/{len(uploaded_files)} (OCR bekerja)...")
                    
                    # Cek Tanggal pada Nama File Awal
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
                    
                    # Klasifikasi Berdasarkan Nama File
                    if any(x in name_only for x in ["WESEL", "WLSE"]): 
                        target_keyword, kode_ceklis, kategori_nama = "WESEL", "BPBYE1", "WESEL"
                    elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL", "ZP"]): 
                        target_keyword, kode_ceklis, kategori_nama = "AXLE", "BPBYE7", "AXC"
                    elif any(x in name_only for x in ["SINYAL", "BLOK"]): 
                        target_keyword, kode_ceklis, kategori_nama = "SINYAL", "BPBYE3", "SINYAL"
                    elif any(x in name_only for x in ["OPTIK", "OPTIC", "SERAT", "OTB"]): 
                        target_keyword, kode_ceklis, kategori_nama = "OPTIK", "BPBKF4", "" 
                    elif any(x in name_only for x in ["TELKOM", "LUAR", "PTLS"]): 
                        target_keyword, kode_ceklis, kategori_nama = "TELKOM_LUAR", "BPBKS16", "PTLS"

                    if target_keyword:
                        try:
                            # Step OCR 1: Convert PDF ke Image
                            images = convert_from_bytes(f.getvalue(), dpi=150, first_page=1, last_page=1)
                            img = ImageOps.autocontrast(images[0].convert('L')) 
                            
                            # Step OCR 2: Crop 50% Atas (Optimasi Kecepatan)
                            width, height = img.size
                            img_cropped = img.crop((0, 0, width, int(height * 0.5)))
                            
                            if debug_mode: 
                                st.image(img_cropped, caption=f"Debug Visual: {f.name}")
                                
                            # Step OCR 3: Ekstraksi Teks Mentah
                            text_crop = pytesseract.image_to_string(img_cropped).upper()
                            lines = [line.strip() for line in text_crop.split('\n') if line.strip()]
                            
                            trace_logs = [] # CCTV Log untuk Admin

                            for line in lines:
                                # ==================== LOGIKA WESEL ====================
                                if target_keyword == "WESEL" and "WSL" in line and ":" in line:
                                    trace_logs.append(f"🔍 [WESEL] Baris: '{line}'")
                                    right_side = line.split(":")[-1].strip()
                                    for noise in ["WESEL ELEKTRIK TERLAYAN SETEMPAT", "WESEL ELEKTRIK", "PENGGERAK WESEL", "WESELPENGGERAK", "PENGGERAK", "ELEKTRIK", "WESEL"]:
                                        right_side = right_side.replace(noise, "")
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
                                        assets_found.append({"id": aid, "loc": loc_id or "LOKASI"})
                                        trace_logs.append(f"✅ OK: {aid}")

                                # ==================== LOGIKA SINYAL ====================
                                elif target_keyword == "SINYAL" and "SIN" in line and ":" in line:
                                    trace_logs.append(f"🔍 [SINYAL] Baris: '{line}'")
                                    right_side = line.split(":")[-1].strip()
                                    # Menghilangkan ULANG BLOK dan DAN LANGSIR sesuai request
                                    for noise in ["DAN LANGSIR", "ULANG BLOK", "SINYAL BLOK", "SINYAL MUKA", "SINYAL MASUK", "SINYAL KELUAR", "SINYAL LANGSIR", "SINYAL", "ULANG", "BLOK"]:
                                        right_side = right_side.replace(noise, "")
                                    words = right_side.strip().split()
                                    if words:
                                        aid, loc_id = words[0], " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                        assets_found.append({"id": aid, "loc": loc_id})
                                        trace_logs.append(f"✅ OK: {aid}")

                                # ==================== LOGIKA SERAT OPTIK (OTB) ====================
                                elif target_keyword == "OPTIK" and "TRA" in line and ":" in line:
                                    trace_logs.append(f"🔍 [OTB] Baris: '{line}'")
                                    right_side = line.split(":")[-1].strip()
                                    for noise in ["SERAT OPTIK", "KABEL OPTIK", "KABEL"]:
                                        right_side = right_side.replace(noise, "")
                                    words = right_side.strip().split()
                                    if words:
                                        # Ambil 2 kata pertama sebagai ID (Misal: OTB 1)
                                        aid = " ".join(words[:2]) if len(words) > 1 else words[0]
                                        loc_id = " ".join(words[2:]) if len(words) > 2 else ""
                                        assets_found.append({"id": aid, "loc": loc_id})
                                        trace_logs.append(f"✅ OK: {aid}")

                                # ==================== LOGIKA TELKOM LUAR (PTLS) ====================
                                elif target_keyword == "TELKOM_LUAR" and "TRA" in line and ":" in line:
                                    trace_logs.append(f"🔍 [PTLS] Baris: '{line}'")
                                    right_side = line.split(":")[-1].strip()
                                    for noise in ["TELEKOMUNIKASI", "TELKOM", "LUAR", "STASIUN", "PTLS", "RADIO", "BASE", "STATION"]:
                                        right_side = right_side.replace(noise, "")
                                    words = right_side.strip().split()
                                    if words:
                                        # ID Aset diabaikan (kata pertama), sisanya lokasi
                                        loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                        assets_found.append({"id": "", "loc": loc_id})
                                        trace_logs.append(f"✅ OK PTLS: {loc_id}")

                            if debug_mode and trace_logs:
                                with st.expander(f"🕵️ Trace Log: {f.name}"):
                                    for log in trace_logs: st.text(log)

                            # Bersihkan RAM setiap selesai 1 file
                            del img, img_cropped, images
                            gc.collect() 
                        except Exception as e:
                            duplicate_errors.append(f"❌ `{f.name}`: Error OCR ({str(e)})")

                    # Finalisasi Nama File Baru
                    if assets_found:
                        for asset in assets_found:
                            aid_clean, aloc_clean = asset["id"].strip(), asset["loc"].strip()
                            # Gabung kategori dan ID tanpa spasi double
                            part_nama = f"{kategori_nama} {aid_clean}".strip()
                            
                            if format_eksklusif:
                                new_name = f"{prefix_periode}_Resor 1.21 Boo_{kode_ceklis}_{jenis_kegiatan}_{part_nama}_{aloc_clean}_{tgl_full}.pdf"
                            else:
                                new_name = f"{jenis_kegiatan.upper()} {part_nama} {aloc_clean} {tgl_full}.pdf"
                            
                            # Menghapus spasi ganda menggunakan Regex
                            new_name = re.sub(r'\s+', ' ', new_name).strip()
                            new_name = new_name.replace("_ ", "_").replace(" _", "_")

                            if new_name not in unique_filenames:
                                zip_f.writestr(new_name, f.getvalue())
                                processed_files.append(new_name)
                                unique_filenames.add(new_name)
                            else:
                                duplicate_errors.append(f"⚠️ `{f.name}`: Duplikat pada `{aid_clean or aloc_clean}`")
                    else:
                        duplicate_errors.append(f"🔍 `{f.name}`: Gagal identifikasi data aset.")

            status_container.empty()
            st.subheader("📋 Hasil Proses")

            # TAMPILAN TOMBOL BERDAMPINGAN
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                # Tombol Download memicu rerun, flag download_done akan menghentikan OCR berikutnya
                if st.download_button(
                    label="📥 DOWNLOAD ZIP", 
                    data=zip_buffer.getvalue(), 
                    file_name="Hasil_Rename_Sintelis_BOO.zip", 
                    mime="application/zip", 
                    use_container_width=True, 
                    type="primary"
                ):
                    st.session_state.download_done = True
                    st.rerun()

            with btn_col2:
                # Tombol Mulai Baru yang pasif sebelum download
                st.button("🔄 MULAI BARU", use_container_width=True, disabled=True)

            with st.expander(f"✅ Berhasil Teridentifikasi ({len(processed_files)})", expanded=True):
                for p_file in processed_files: st.write(f"📄 `{p_file}`")
            if duplicate_errors:
                with st.expander("❌ Masalah Ditemukan", expanded=True):
                    for err in duplicate_errors: st.warning(err)
        
        else:
            # TAMPILAN SETELAH TOMBOL DOWNLOAD DIKLIK
            st.success("✅ File ZIP berhasil diunduh ke komputer Anda!")
            if st.button("🔄 MULAI BARU / RESET", use_container_width=True, type="primary"):
                st.session_state.download_done = False
                st.session_state["file_uploader_key"] += 1
                st.rerun()

# --- 5. FOOTER ---
st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dika Armansyah</b> | Sintelis 1.21 BOO Utility</div>", unsafe_allow_html=True)