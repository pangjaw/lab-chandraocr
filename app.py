import streamlit as st
import re
import os
import zipfile
import json
import hashlib
from io import BytesIO
from google.cloud import firestore
from google.oauth2 import service_account

# --- 1. KEAMANAN (HASHING) ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- 2. KONEKSI FIRESTORE ---
if "firebase" in st.secrets:
    key_dict = dict(st.secrets["firebase"])
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
    
    creds = service_account.Credentials.from_service_account_info(key_dict)
    db = firestore.Client(credentials=creds, project=key_dict['project_id'])
else:
    st.error("Konfigurasi Firebase tidak ditemukan di Secrets!")
    st.stop()

# --- 3. FUNGSI DATABASE ---
def get_user_db(email):
    doc_ref = db.collection("users").document(email)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("mapping", {})
    return {"BOGOR": "BOO"} # Default awal

def save_user_db(email, mapping):
    db.collection("users").document(email).set({"mapping": mapping})

def import_user_db(email, new_mapping):
    # Menggabungkan data lama dengan data baru (Update)
    current_mapping = get_user_db(email)
    current_mapping.update(new_mapping) 
    save_user_db(email, current_mapping)
    return current_mapping

def save_bulk_user_db(email, df_mapping):
    # Mengubah DataFrame kembali ke format dictionary {LOKASI: KODE}
    new_dict = dict(zip(df_mapping['Lokasi'], df_mapping['Singkatan']))
    # Filter agar baris kosong tidak ikut tersimpan
    clean_dict = {k.strip().upper(): v.strip().upper() for k, v in new_dict.items() if k and v}
    db.collection("users").document(email).set({"mapping": clean_dict})
    return clean_dict

# --- 4. LOGIKA LOGIN MANDIRI ---
if 'connected' not in st.session_state:
    st.session_state.connected = False

if not st.session_state.connected:
    st.title("🔐 Login Ceklis Sintelis")
    email_input = st.text_input("Email/Username").lower().strip()
    pass_input = st.text_input("Password", type="password")
    
    col1, col2 = st.columns(2)
    
    if col1.button("Login", use_container_width=True):
        user_cred = db.collection("credentials").document(email_input).get()
        if user_cred.exists:
            stored_password = user_cred.to_dict().get("password")
            if hash_password(pass_input) == stored_password:
                st.session_state.connected = True
                st.session_state.user_email = email_input
                st.session_state.user_name = email_input.split("@")[0].upper()
                st.rerun()
            else:
                st.error("Password salah!")
        else:
            st.error("User tidak terdaftar!")

    if col2.button("Daftar Akun Baru", use_container_width=True):
        if email_input and pass_input:
            db.collection("credentials").document(email_input).set({
                "password": hash_password(pass_input)
            })
            st.success("Akun berhasil dibuat! Silakan klik Login.")
        else:
            st.warning("Isi email dan password untuk mendaftar.")
    st.stop()

# --- SETELAH LOGIN ---
user_email = st.session_state.user_email
user_name = st.session_state.user_name

if 'mapping_lokasi' not in st.session_state:
    st.session_state.mapping_lokasi = get_user_db(user_email)

# --- 5. CALLBACK DATABASE ---
def add_location_callback():
    val = st.session_state.input_baru
    if "=" in val:
        k, v = val.split("=")
        st.session_state.mapping_lokasi[k.strip().upper()] = v.strip().upper()
        save_user_db(user_email, st.session_state.mapping_lokasi)
        st.toast(f"Tersimpan: {k.strip().upper()}", icon="✅")
    st.session_state.input_baru = ""

def delete_location(key_to_delete):
    if key_to_delete in st.session_state.mapping_lokasi:
        del st.session_state.mapping_lokasi[key_to_delete]
        save_user_db(user_email, st.session_state.mapping_lokasi)
        st.toast(f"Dihapus: {key_to_delete}", icon="🗑️")

# --- 6. UI SIDEBAR ---
import pandas as pd

with st.sidebar:
    # 1. Header Profil
    st.write(f"Halo, **{user_name}**")
    st.write(f"📧 {user_email}")
    st.divider()

    # 2. Menu Navigasi (Hanya 2 Menu Utama)
    menu_pilihan = st.radio(
        "Pilih Menu:",
        ["📍 Kelola Lokasi", "📦 Backup & Restore"]
    )

    st.divider()

    # --- KONDISI MENU 1: KELOLA LOKASI (Tabel Statis & Form) ---
    if menu_pilihan == "📍 Kelola Lokasi":
        st.subheader("Daftar Lokasi")
        
        if st.session_state.mapping_lokasi:
            # Membuat DataFrame untuk tampilan tabel yang bersih
            df_view = pd.DataFrame([
                {"Lokasi": k, "Singkatan": v} 
                for k, v in st.session_state.mapping_lokasi.items()
            ])
            # Tampilkan tabel statis (tidak bisa diedit langsung)
            st.table(df_view)
        else:
            st.info("Database kosong.")

        st.divider()
        
        # Form Input untuk Tambah/Update
        st.subheader("Tambah/Update")
        with st.form("form_lokasi", clear_on_submit=True):
            l_input = st.text_input("Nama Lokasi").upper().strip()
            s_input = st.text_input("Singkatan").upper().strip()
            submit = st.form_submit_button("Simpan ke Database", use_container_width=True)
            
            if submit:
                if l_input and s_input:
                    st.session_state.mapping_lokasi[l_input] = s_input
                    db.collection("users").document(user_email).set({"mapping": st.session_state.mapping_lokasi})
                    st.success(f"Tersimpan: {l_input}")
                    st.rerun()
                else:
                    st.error("Isi kedua kolom!")

        # Fitur Hapus
        if st.session_state.mapping_lokasi:
            st.divider()
            st.subheader("Hapus Data")
            opsi_hapus = list(st.session_state.mapping_lokasi.keys())
            target = st.selectbox("Pilih yang akan dihapus:", ["-- Pilih --"] + opsi_hapus)
            if st.button("🗑️ Hapus Permanen", use_container_width=True) and target != "-- Pilih --":
                del st.session_state.mapping_lokasi[target]
                db.collection("users").document(user_email).set({"mapping": st.session_state.mapping_lokasi})
                st.toast(f"{target} dihapus")
                st.rerun()

    # --- KONDISI MENU 2: BACKUP & RESTORE ---
    elif menu_pilihan == "📦 Backup & Restore":
        st.subheader("Export/Import Data")
        
        # Export
        js_data = json.dumps(st.session_state.mapping_lokasi, indent=4)
        st.download_button(
            label="📥 Download Backup (.json)",
            data=js_data,
            file_name=f"backup_lokasi_{user_name}.json",
            mime="application/json",
            use_container_width=True
        )

        st.divider()

        # Import
        st.write("Upload file .json untuk menambah data:")
        file_up = st.file_uploader("Pilih file", type="json")
        if file_up:
            try:
                data_up = json.load(file_up)
                if isinstance(data_up, dict):
                    st.session_state.mapping_lokasi.update(data_up)
                    db.collection("users").document(user_email).set({"mapping": st.session_state.mapping_lokasi})
                    st.success("Import Berhasil!")
                    st.rerun()
            except:
                st.error("File tidak valid!")

    # 3. TOMBOL LOGOUT (Selalu Tampil di Paling Bawah Sidebar)
    # Kita berikan banyak divider atau spasi kosong agar terdorong ke bawah
    st.write("---") 
    if st.button("🚪 Log Out", use_container_width=True, type="secondary"):
        st.session_state.connected = False
        st.session_state.user_email = None
        st.session_state.user_name = None
        st.rerun()

# --- 7. HALAMAN UTAMA: PROSES FILE ---
st.title("🚀 Pemroses Nama Ceklis")
kode_opsi = ["BPBKS1", "BPBKF1", "BPBYE1"]
selected_kode = st.selectbox("Pilih Kode Unit:", kode_opsi)

uploaded_files = st.file_uploader("Upload PDF (Bisa banyak sekaligus)", type="pdf", accept_multiple_files=True)

if uploaded_files:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for uploaded_file in uploaded_files:
            name_only = os.path.splitext(uploaded_file.name)[0]
            tgl_match = re.search(r'\d{2}-\d{2}-\d{4}', name_only)
            if not tgl_match:
                st.warning(f"⚠️ {name_only}: Tanggal tidak ditemukan.")
                continue
            
            tgl = tgl_match.group()
            tahun, bulan = tgl.split("-")[-1], int(tgl.split("-")[1])

            found_full, found_short = None, None
            name_no_space = name_only.upper().replace(" ", "")

            for k, v in st.session_state.mapping_lokasi.items():
                if k.upper().replace(" ", "") in name_no_space or v.upper().replace(" ", "") in name_no_space:
                    found_full, found_short = k, v
                    break
            
            if not found_short:
                st.error(f"❌ {name_only}: Lokasi tidak ada di database!")
                continue

            clean = name_only.upper().replace(tgl, "").replace(str(found_full), "").replace(str(found_short), "").strip("_ ")
            parts = clean.split("_")
            perawatan_parts, assets = [], []

            for p in parts:
                p = p.strip()
                if "," in p:
                    assets.extend([a.strip() for a in p.split(",") if a.strip()])
                elif any(char.isdigit() for char in p) and not any(x in p for x in ["MINGGUAN", "BULANAN", "TAHUNAN"]):
                    assets.append(p)
                elif p != "":
                    perawatan_parts.append(p)
            
            if not assets:
                manual_a = st.text_input(f"Aset untuk {name_only} (pisah koma):", key=f"m_{name_only}")
                if manual_a:
                    assets = [a.strip() for a in manual_a.split(",")]
                else:
                    continue

            nama_perawatan = "_".join(perawatan_parts).replace(" ", "_").strip("_")
            for asset in assets:
                new_name = f"{tahun}-{bulan}_Resor 1.21 Boo_{selected_kode}_{nama_perawatan}_{asset}_{found_short}_{tgl}.pdf"
                zip_file.writestr(new_name, uploaded_file.getvalue())
                st.success(f"Berhasil diproses: {new_name}")

    st.divider()
    st.download_button(
        label="📥 Download Semua File (.ZIP)",
        data=zip_buffer.getvalue(),
        file_name="Ceklis_Sintelis_Done.zip",
        use_container_width=True
    )