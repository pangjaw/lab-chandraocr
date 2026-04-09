import streamlit as st
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sintelis Sandbox Lab", layout="wide")

st.title("🛠️ SINTELIS LOGIC LAB (OPSI 2)")
st.info("Halaman ini digunakan untuk 'ngoprek' logika penamaan tanpa merusak script utama.")

# Kita bagi layar jadi dua: Kiri (Editor), Kanan (Hasil)
col_editor, col_preview = st.columns([1.2, 1], gap="large")

with col_editor:
    st.subheader("📝 Script Editor")
    # Di sini tempat Mas Dika ngetik/edit script penamaan
    user_code = st.text_area(
        "Edit Logika Penamaan di Sini:", 
        height=400,
        value="""# Tulis logika kamu di bawah ini
# Gunakan variabel: name_only, ocr_text, tgl

if "PINTU PERLINTASAN" in name_only:
    # Contoh eksperimen: ambil nomor JPL saja
    jpl_match = re.search(r'JPL\s?(\d+)', ocr_text)
    nomor = jpl_match.group(1) if jpl_match else "???"
    
    # Contoh format baru yang mau diuji
    nama_baru = f"PERAWATAN_JPL_{nomor}_STASIUN_BOGOR_{tgl}.pdf"
    
    st.markdown(f"### 🎯 Hasil Simulasi:")
    st.success(nama_baru)
else:
    st.warning("Kata kunci tidak cocok dengan input simulasi di kanan.")
"""
    )

with col_preview:
    st.subheader("📺 Simulasi Input & Output")
    
    # Masukkan contoh data untuk ngetes script di sebelah kiri
    input_file = st.text_input("1. Simulasi Nama File Asli:", "CEKLIS PINTU PERLINTASAN JANUARI.pdf")
    input_ocr = st.text_area("2. Simulasi Hasil OCR Dokumen:", "PT KAI - FORM CEKLIS JPL 27 - TANGGAL 15-03-2026")
    input_tgl = st.text_input("3. Simulasi Tanggal (DD-MM-YYYY):", "15-03-2026")
    
    st.divider()
    
    if st.button("🚀 JALANKAN LOGIKA", use_container_width=True, type="primary"):
        st.write("---")
        try:
            # Kita siapkan 'ruangan' (environment) agar script di editor
            # bisa mengenali variabel name_only, ocr_text, dan tgl.
            scope = {
                "re": re, 
                "st": st, 
                "name_only": input_file.upper(), 
                "ocr_text": input_ocr.upper(), 
                "tgl": input_tgl
            }
            
            # Perintah sakti: menjalankan string teks sebagai kode Python
            exec(user_code, {}, scope)
            
        except Exception as e:
            st.error(f"❌ Terjadi Error di Script Mas:\n{e}")

st.sidebar.title("Instruksi Lab")
st.sidebar.write("""
1. Masukkan data simulasi di kolom kanan.
2. Edit rumus penamaan di kolom kiri.
3. Klik **Jalankan Logika**.
4. Jika sudah oke, copy kodenya ke script utama web Mas.
""")