import streamlit as st
import json
import re
import zipfile
import pypdf
import gc 
from io import BytesIO
from streamlit_lottie import st_lottie

# --- 1. UTILITY FUNCTIONS ---
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
st.set_page_config(page_title="Sintelis 1.21 BOO Utility (Digital PDF)", page_icon="📑", layout="wide")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS (DIGITAL VERSION)")

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
            debug_mode = st.checkbox("Aktifkan Layar Intip Teks Asli PDF", value=False)
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
                
                assets_found, target_keyword, kode_ceklis, kategori_nama = [], None, "", ""
                
                # Pindahkan "ZP" ke kelompok AXLE, dan hapus dari kelompok SINYAL
                if any(x in name_only for x in ["WESEL", "WLSE"]): 
                    target_keyword, kode_ceklis, kategori_nama = "WESEL", "BPBYE1", "WESEL"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL", "ZP"]): # <--- ZP SEKARANG ADA DI SINI
                    target_keyword, kode_ceklis, kategori_nama = "AXLE", "BPBYE7", "AXC"
                elif any(x in name_only for x in ["SINYAL", "BLOK"]): # <--- ZP SUDAH DIHAPUS DARI SINI
                    target_keyword, kode_ceklis, kategori_nama = "SINYAL", "BPBYE3", "SINYAL"
                elif any(x in name_only for x in ["OPTIK", "OPTIC", "SERAT", "OTB", "TRA"]): 
                    target_keyword, kode_ceklis, kategori_nama = "OPTIK", "BPBKF4", "Serat Optik"

                if target_keyword:
                    try:
                        # 1. EKSTRAKSI TEKS DIRECTLY DENGAN PYPDF
                        pdf_file = BytesIO(f.getvalue())
                        reader = pypdf.PdfReader(pdf_file)
                        page_text = reader.pages[0].extract_text()
                        
                        if not page_text or page_text.strip() == "":
                            duplicate_errors.append(f"❌ `{f.name}`: PDF terdeteksi kosong/berupa Gambar Hasil Scan.")
                            continue

                        text_upper = page_text.upper()
                        lines = [line.strip() for line in text_upper.split('\n') if line.strip()]
                        
                        if debug_mode:
                            with st.expander(f"🔍 Teks Ekstraksi Asli: {f.name}", expanded=False):
                                st.text(page_text)

                        # 2. PROSES SCANNING MULTI-LINE BERDASARKAN POLA INTERNAL KAI
                        for line in lines:
                            
                            # ==================== KATEGORI WESEL ====================
                            if target_keyword == "WESEL" and "WSL" in line and ":" in line:
                                right_side = line.split(":")[-1].strip()
                                
                                right_side = right_side.replace("WESEL ELEKTRIK TERLAYAN SETEMPAT", "")
                                right_side = right_side.replace("WESEL ELEKTRIK", "")
                                right_side = right_side.replace("PENGGERAK WESEL", "")
                                right_side = right_side.replace("WESELPENGGERAK", "")
                                
                                right_side = right_side.replace("PENGGERAK", "")
                                right_side = right_side.replace("ELEKTRIK", "")
                                right_side = right_side.replace("WESEL", "").strip()
                                
                                words = right_side.split()
                                if words:
                                    aid = words[0] if words[0].startswith("W") else f"W{words[0]}"
                                    loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    assets_found.append({"id": aid, "loc": loc_id})

                            # ==================== KATEGORI AXLE COUNTER ====================
                            elif target_keyword == "AXLE" and "AXL" in line and ":" in line:
                                right_side = line.split(":")[-1].strip()
                                
                                right_side = right_side.replace("AXLE.COUNTER.", "").replace("AXLE COUNTER", "")
                                right_side = right_side.replace(".", " ").strip() 
                                
                                words = right_side.split()
                                if words:
                                    if words[0] == "ZP" and len(words) > 1:
                                        aid = f"ZP {words[1]}"
                                        loc_id = " ".join(words[2:]) if len(words) > 2 else "LOKASI"
                                    else:
                                        aid = words[0] if words[0].startswith("ZP") else f"ZP{words[0]}"
                                        loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    assets_found.append({"id": aid, "loc": loc_id})

                            # ==================== KATEGORI SINYAL ====================
                            elif target_keyword == "SINYAL" and "SIN" in line and ":" in line:
                                right_side = line.split(":")[-1].strip()
                                
                                for jenis_sinyal in ["SINYAL BLOK", "SINYAL MUKA", "SINYAL MASUK", "SINYAL KELUAR", "SINYAL LANGSIR"]:
                                    right_side = right_side.replace(jenis_sinyal, "")
                                
                                right_side = right_side.replace("SINYAL", "").strip()
                                
                                words = right_side.split()
                                if words:
                                    aid = words[0]
                                    loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    assets_found.append({"id": aid, "loc": loc_id})

                            # ==================== KATEGORI SERAT OPTIK ====================
                            elif target_keyword == "OPTIK" and "TRA" in line and ":" in line:
                                right_side = line.split(":")[-1].strip()
                                
                                for noise in ["SERAT OPTIK", "KABEL OPTIK", "KABEL"]:
                                    right_side = right_side.replace(noise, "")
                                right_side = right_side.strip()
                                
                                words = right_side.split()
                                if words:
                                    if words[0] == "OTB" and len(words) > 1:
                                        aid = f"OTB {words[1]}"
                                        loc_id = " ".join(words[2:]) if len(words) > 2 else "LOKASI"
                                    else:
                                        aid = words[0] if words[0].startswith("OTB") else f"OTB {words[0]}"
                                        loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    
                                    assets_found.append({"id": aid, "loc": loc_id})

                        gc.collect() 
                    except Exception as e:
                        duplicate_errors.append(f"❌ `{f.name}`: Error Membaca PDF ({str(e)})")

                if assets_found:
                    for asset in assets_found:
                        aid_clean = asset["id"].strip()
                        aloc_clean = asset["loc"].strip()
                        
                        if format_eksklusif:
                            new_name = f"{prefix_periode}_Resor 1.21 Boo_{kode_ceklis}_{jenis_kegiatan}_{kategori_nama}_{aid_clean}_{aloc_clean}_{tgl_full}.pdf"
                        else:
                            new_name = f"{jenis_kegiatan.upper()} {kategori_nama} {aid_clean} {aloc_clean} {tgl_full}.pdf"

                        if new_name not in unique_filenames:
                            zip_f.writestr(new_name, f.getvalue())
                            processed_files.append(new_name)
                            unique_filenames.add(new_name)
                        else:
                            duplicate_errors.append(f"⚠️ `{f.name}`: ID `{aid_clean}` duplikat.")
                else:
                    if f.name not in [e.split("`")[1] for e in duplicate_errors if "`" in e]:
                        duplicate_errors.append(f"🔍 `{f.name}`: Gagal identifikasi ID Aset di dalam teks.")

        status_container.empty()

        if processed_files:
            with btn_col:
                st.download_button(label="📥 DOWNLOAD ZIP", data=zip_buffer.getvalue(), file_name="Hasil_Rename_Sintelis_BOO.zip", mime="application/zip", use_container_width=True, type="primary")

        with st.expander(f"✅ Sukses Teridentifikasi ({len(processed_files)})", expanded=True):
            if processed_files:
                with st.container(height=150):
                    for p_file in processed_files: st.write(f"📄 `{p_file}`")
            else:
                st.write("Belum ada file yang berhasil diproses.")

        with st.expander(f"❌ Gagal Diproses ({len(duplicate_errors)})", expanded=True):
            if duplicate_errors:
                with st.container(height=150):
                    for err in duplicate_errors: st.warning(err)
            else:
                st.write("Tidak ada kendala pada file.")

st.markdown("---")
st.markdown("<div style='text-align: center; color: grey;'>Developed by <b>Dikha Armansyah</b> | Sintelis 1.21 BOO Utility</div>", unsafe_allow_html=True)