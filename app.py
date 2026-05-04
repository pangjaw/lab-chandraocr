import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import re
import io

# --- FUNGSI LOGIKA ---
def clean_asset_name(text):
    """
    Mengambil kode aset saja (J20, UB201, dll) dan mengabaikan keterangan posisi.
    """
    # Regex mencari pola kode teknis: 1-3 huruf kapital, diikuti 2-4 angka, dan opsional 1 huruf di akhir
    asset_pattern = r"\b[A-Z]{1,3}\d{2,4}[A-Z]?\b"
    matches = re.findall(asset_pattern, text.upper())
    
    # Menghapus duplikasi ID aset dalam satu halaman
    return list(dict.fromkeys(matches)) if matches else []

def extract_info(text):
    """
    Ekstraksi Lokasi (3 huruf kapital) dan Tanggal (YYYY-MM-DD -> DD-MM-YYYY).
    """
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    tanggal = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}" if date_match else "00-00-0000"
    
    loc_match = re.search(r"\b([A-Z]{3})\b", text)
    lokasi = loc_match.group(1) if loc_match else "LOKASI"
    
    return lokasi, tanggal

# --- UI STREAMLIT ---
st.title("Sintelis 1.21 BOO Utility")

# Fitur Multiple Files
uploaded_files = st.file_uploader("Upload Dokumen PDF Perawatan", type="pdf", accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.write(f"--- Memproses: {uploaded_file.name} ---")
        
        file_bytes = uploaded_file.read()
        images = convert_from_bytes(file_bytes)
        
        all_detected_files = []

        for img in images:
            # AREA CROP: Gunakan variabel img langsung jika ingin full page, 
            # atau tambahkan .crop() sesuai koordinat final Anda sebelumnya.
            text = pytesseract.image_to_string(img) 
            
            lokasi, tanggal = extract_info(text)
            ids = clean_asset_name(text)
            
            for asset_id in ids:
                # Format: [Perawatan] [Nama Aset] [Lokasi] [Tanggal]
                new_filename = f"PERAWATAN {asset_id} {lokasi} {tanggal}.pdf"
                if new_filename not in all_detected_files:
                    all_detected_files.append(new_filename)

        if all_detected_files:
            for name in all_detected_files:
                st.code(name)
        else:
            st.warning(f"Aset tidak ditemukan pada: {uploaded_file.name}")

st.divider()
# Baris 73 yang sebelumnya error sudah diperbaiki di sini:
st.caption("Developed by Dika Armansyah | Sintelis 1.21 BOO Utility")
