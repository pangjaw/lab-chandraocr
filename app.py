import streamlit as st
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
