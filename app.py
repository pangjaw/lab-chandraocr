import streamlit as st
import re
import os
import zipfile
import platform
import pytesseract
from io import BytesIO
from pdf2image import convert_from_bytes

# --- 1. KONFIGURASI OCR ---
if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- 2. TAMPILAN UTAMA ---
st.set_page_config(page_title="Ganti Nama File Ceklis Sintelis", page_icon="📑")
st.title("📑 GANTI NAMA FILE CEKLIS SINTELIS")
st.info("Format Output: PERAWATAN [ASET] [LOKASI] [TANGGAL]")

use_ocr = st.checkbox("Gunakan OCR (Deteksi Otomatis Nomor Aset & Lokasi)", value=True)
uploaded_files = st.file_uploader("Upload PDF (Bisa banyak sekaligus)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    processed_files = [] # List untuk menampung log file yang berhasil
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_f:
        for f in uploaded_files:
            name_only = os.path.splitext(f.name)[0]
            
            # 1. Cari Tanggal dari Nama File Asli
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {f.name}: Tanggal tidak ditemukan (format harus DD-MM-YYYY).")
                continue
            tgl = tgl_match.group()

            assets = []
            found_short = "LOKASI_TIDAK_TERDETEKSI"
            
            try:
                # 2. Proses Gambar untuk OCR
                images = convert_from_bytes(f.getvalue(), dpi=300)
                img = images[0]
                width, height = img.size

                if use_ocr:
                    # A. DETEKSI ASET (Fokus area kanan atas)
                    left, top, right, bottom = width*0.55, height*0.05, width*0.98, height*0.55
                    img_cropped = img.crop((left, top, right, bottom))
                    text_aset = pytesseract.image_to_string(img_cropped)
                    
                    match_aset = re.findall(r'(?:WESEL|BLOK|SINYAL|COUNTER)\s+([M|J|B|W|ZP|UB]{1,2}\.?\s?\d+[A-Z]?)', text_aset, re.IGNORECASE)
                    
                    if match_aset:
                        cleaned = [a.upper().replace(".", "").replace(" ", "") for a in match_aset]
                        for item in cleaned:
                            if item not in assets: assets.append(item)
                        assets = assets[:5]

                    # B. DETEKSI LOKASI
                    full_text = pytesseract.image_to_string(img).upper()
                    loc_pair = re.search(r'([A-Z]{3,4}\-[A-Z]{3,4})', full_text)
                    loc_single = re.findall(r'\b(BOO|CTA|PSM|MRI|DP|DPB|CIT|BJD|GDD|JAKK|KPB)\b', full_text)

                    if loc_pair: 
                        found_short = loc_pair.group().upper()
                    elif loc_single: 
                        found_short = loc_single[0]
                    elif "BOGOR" in full_text: 
                        found_short = "BOO"

            except Exception as e:
                st.error(f"Gagal memproses {f.name}: {e}")
                continue

            # 3. Fallback & Penamaan
            if not assets:
                assets = [p for p in name_only.upper().split("_") if any(c.isdigit() for c in p)][:1]
            
            if assets:
                for asset in assets:
                    new_name = f"PERAWATAN {asset} {found_short} {tgl}.pdf"
                    zip_f.writestr(new_name, f.getvalue())
                    processed_files.append(new_name)

    # --- 3. DISPLAY LOG (SCROLLABLE) ---
    if processed_files:
        st.write("### 📋 Log Hasil Proses:")
        # Menggunakan st.container dengan height membuat area menjadi scrollable otomatis
        with st.container(height=250):
            for p_file in processed_files:
                st.write(f"✅ `{p_file}`")

    # --- 4. TOMBOL DOWNLOAD OTOMATIS ---
    st.divider()
    if zip_buffer.getbuffer().nbytes > 0:
        st.download_button(
            label="📥 DOWNLOAD SEMUA HASIL (.ZIP)",
            data=zip_buffer.getvalue(),
            file_name="Hasil_Rename_Sintelis.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary"
        )

# --- 5. FOOTER KREDIT ---
st.markdown("---")
st.markdown(
    """
    <style>
    .footer {
        text-align: center;
        color: grey;
        font-size: 14px;
    }
    </style>
    <div class="footer">
        Developed by <b>Dika Armansyah</b> | Sintelis KAI Utility
    </div>
    """,
    unsafe_allow_html=True
)