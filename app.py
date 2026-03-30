import streamlit as st
import re
import os
import zipfile
from io import BytesIO

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Editor Nama Ceklis", page_icon="📝")

# --- DATABASE LOKASI (HASHTABLE) ---
# Di Streamlit Cloud, kita bisa simpan sementara di session_state
if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = {
        "BOGOR": "BOO",
        "CILEBUT": "CLT",
        "BOGORPALEDANG": "BPB"
    }

st.title("📝 Auto-Rename & Duplicate PDF")
st.write("Upload file PDF, dan sistem akan merubah namanya sesuai standar Resor 1.21.")

# --- SIDEBAR: DATABASE LOKASI ---
with st.sidebar:
    st.header("Settings Database")
    new_input = st.text_input("Tambah Lokasi (Contoh: MASENG=MSG)")
    if st.button("Update Database"):
        if "=" in new_input:
            k, v = new_input.split("=")
            st.session_state.mapping_lokasi[k.strip().upper()] = v.strip().upper()
            st.success(f"Berhasil simpan {k.strip().upper()}")

    st.write("Daftar Database Saat Ini:")
    st.json(st.session_state.mapping_lokasi)

# --- FORM INPUT UTAMA ---
kode_opsi = ["BPBKS1", "BPBKF1", "BPBYE1"]
selected_kode = st.selectbox("Pilih Kode Unit:", kode_opsi)

uploaded_files = st.file_uploader("Drag & Drop File PDF di sini", type="pdf", accept_multiple_files=True)

if uploaded_files:
    st.subheader("Proses File")
    all_processed_files = [] # Untuk menyimpan file yang sudah jadi
    
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
        
        for uploaded_file in uploaded_files:
            name_only = os.path.splitext(uploaded_file.name)[0]
            
            # 1. Cari Tanggal dd-mm-yyyy
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.error(f"Gagal: {name_only} (Tidak ada tanggal)")
                continue
            
            tgl = tgl_match.group()
            tahun = tgl.split("-")[-1]
            bulan = int(tgl.split("-")[1])

            # 2. Cari Lokasi
            found_full = None
            found_short = None
            for key, val in st.session_state.mapping_lokasi.items():
                if key in name_only.upper() or val in name_only.upper():
                    found_full = key
                    found_short = val
                    break
            
            if not found_short:
                st.warning(f"Lokasi tidak dikenal di file: {name_only}")
                found_short = st.text_input(f"Singkatan Lokasi untuk '{name_only}'?", key=name_only)
                if not found_short: continue

            # 3. Bersihkan Nama & Cari Aset
            clean = name_only.upper().replace(tgl, "").replace(str(found_full), "").replace(str(found_short), "").strip("_ ")
            parts = clean.split("_")
            perawatan_parts = []
            assets = []

            for p in parts:
                p = p.strip()
                if "," in p:
                    assets.extend([a.strip() for a in p.split(",")])
                elif any(char.isdigit() for char in p) and not any(x in p for x in ["MINGGUAN", "BULANAN", "TAHUNAN"]):
                    assets.append(p)
                elif p != "":
                    perawatan_parts.append(p)
            
            # --- INPUT MANUAL JIKA ASET ERROR ---
            if len(assets) <= 1 and "," not in name_only:
                st.info(f"File: {name_only}")
                manual_assets = st.text_input(f"Ketik Aset (pisahkan koma) untuk {name_only}:", placeholder="Contoh: 10A,10B", key=f"man_{name_only}")
                if manual_assets:
                    assets = [a.strip() for a in manual_assets.split(",")]
                else:
                    st.write("Menunggu input aset manual...")
                    continue

            nama_perawatan = "_".join(perawatan_parts).replace(" ", "_").strip("_")

            # 4. Buat File Baru ke dalam ZIP
            for asset in assets:
                if not asset: continue
                new_name = f"{tahun}-{bulan}_Resor 1.21 Boo_{selected_kode}_{nama_perawatan}_{asset}_{found_short}_{tgl}.pdf"
                
                # Copy isi file asli ke nama baru di dalam ZIP
                zip_file.writestr(new_name, uploaded_file.getvalue())
                st.success(f"Siap dibuat: {new_name}")

    # --- TOMBOL DOWNLOAD ---
    st.divider()
    if st.download_button(
        label="📥 Download Semua Hasil (.ZIP)",
        data=zip_buffer.getvalue(),
        file_name="Hasil_Rename_Ceklis.zip",
        mime="application/zip"
    ):
        st.balloons()
