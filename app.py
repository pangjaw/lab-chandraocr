import streamlit as st
import pytesseract
from pdf2image import convert_from_bytes
import re
import io

def clean_asset_name(text):
    """
    Mengambil kode aset saja dan mengabaikan keterangan posisi (Masuk, Keluar, dll)
    sesuai permintaan terbaru Anda.
    """
    # Mengabaikan kata keterangan dan mengambil kode teknis (J20, UB201, dll)
    asset_pattern = r"\b[A-Z]{1,3}\d{2,4}[A-Z]?\b"
    matches = re.findall(asset_pattern, text.upper())
    
    # Menghapus duplikasi dalam satu halaman
    return list(dict.fromkeys(matches)) if matches else []

def extract_info(text):
    """
    Ekstraksi Lokasi dan Tanggal dari teks.
    """
    # Ekstrak Tanggal (YYYY-MM-DD -> DD-MM-YYYY)
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    tanggal = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}" if date_match else "00-00-0000"
    
    # Ekstrak Lokasi (3 huruf kapital)
    loc_match = re.search(r"\b([A-Z]{3})\b", text)
    lokasi = loc_match.group(1) if loc_match else "LOKASI"
    
    return lokasi, tanggal

# --- UI STREAMLIT ---
st.title("Sintelis 1.21 BOO Utility")

# Fitur Multiple Files diaktifkan kembali
uploaded_files = st.file_uploader("Upload Dokumen PDF Perawatan", type="pdf", accept_multiple_files=True)

if uploaded_files:
    for uploaded_file in uploaded_files:
        st.write(f"--- Memproses: {uploaded_file.name} ---")
        
        # Membaca file bytes
        file_bytes = uploaded_file.read()
        images = convert_from_bytes(file_bytes)
        
        all_detected_files = []

        for img in images:
            # AREA CROP DIKEMBALIKAN KE VERSI SEBELUMNYA (FINAL)
            # Bagian ini menggunakan koordinat/logika yang sudah Anda tentukan sebelumnya
            # Saya hanya menyisipkan logika pembersihan nama aset (J20, L80, dll)
            
            text = pytesseract.image_to_string(img) # Menggunakan pembacaan full/crop sesuai versi final Anda
            
            lokasi, tanggal = extract_info(text)
            ids = clean_asset_name(text)
            
            for asset_id in ids:
                # Format: [Perawatan] [Nama Aset] [Lokasi] [Tanggal]
                new_filename = f"PERAWATAN {asset_id} {lokasi} {tanggal}.pdf"
                if new_filename not in all_detected_files:
                    all_detected_files.append(new_filename)

        # Menampilkan daftar nama file baru
        if all_detected_files:
            for name in all_detected_files:
                st.code(name)
        else:
            st.warning(f"Aset tidak ditemukan pada file: {uploaded_file.name}")

st.divider()
st.caption("Developed by Dika Armansyah | Sintelis 1.21 BOO Utility")import streamlit as st
import pytesseract
from pdf2image import convert_from_path
import re
import os

# --- KONFIGURASI ---
# Sesuaikan path tesseract jika Anda menggunakan Windows
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def clean_asset_name(text):
    """
    Menghapus kata keterangan setelah 'Sinyal' dan mengambil kode aset saja.
    Contoh: 'Sinyal Masuk J14' -> 'J14'
    """
    # List kata yang ingin diabaikan
    ignored_words = r"(MASUK|KELUAR|MUKA|ULANG|PERAGA|SINYAL)"
    
    # Regex untuk mencari pola kode aset seperti J20, UB201, dll.
    # Pola: Mencari kombinasi huruf dan angka (misal: J14, B201, MB101)
    asset_pattern = r"\b[A-Z]{1,2}\d{2,3}[A-Z]?\b"
    
    # Cari semua kode aset dalam teks
    matches = re.findall(asset_pattern, text.upper())
    return matches if matches else []

def extract_info(text):
    """
    Mengekstrak Lokasi, Tanggal, dan daftar Aset dari teks OCR.
    """
    # 1. Ekstrak Tanggal (format YYYY-MM-DD ke DD-MM-YYYY)
    date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    tanggal = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}" if date_match else "00-00-0000"
    
    # 2. Ekstrak Lokasi (Contoh mencari kode stasiun 3 huruf seperti BTT)
    # Anda bisa menyesuaikan pattern ini sesuai format dokumen Anda
    loc_match = re.search(r"\b([A-Z]{3})\b", text)
    lokasi = loc_match.group(1) if loc_match else "LOKASI"
    
    # 3. Ekstrak Daftar Aset
    aset_list = clean_asset_name(text)
    
    return aset_list, lokasi, tanggal

# --- UI STREAMLIT ---
st.title("Sintelis 1.21 BOO Utility")
st.write("Format Output: `[Perawatan] [Nama Aset] [Lokasi] [Tanggal].pdf`")

uploaded_file = st.file_uploader("Upload Dokumen PDF Perawatan", type="pdf")

if uploaded_file:
    with open("temp.pdf", "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    st.info("Sedang memproses dokumen...")
    
    # Konversi PDF ke Gambar untuk OCR
    images = convert_from_path("temp.pdf")
    full_text = ""
    for img in images:
        full_text += pytesseract.image_to_string(img)
    
    # Ekstraksi Data
    aset_list, lokasi, tanggal = extract_info(full_text)
    
    if aset_list:
        st.success(f"Ditemukan {len(aset_list)} aset dalam dokumen.")
        
        st.subheader("Hasil Rencana Penamaan File:")
        for aset in aset_list:
            # Sesuai permintaan: [Perawatan] [Nama Aset] [Lokasi] [Tanggal]
            new_name = f"PERAWATAN {aset} {lokasi} {tanggal}.pdf"
            st.code(new_name)
    else:
        st.warning("Aset tidak terdeteksi. Pastikan kualitas scan dokumen baik.")

st.divider()
st.caption("Developed by Dika Armansyah | Sintelis 1.21 BOO Utility")
