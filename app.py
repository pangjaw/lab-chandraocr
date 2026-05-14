# ... existing code ...

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
                
                if any(x in name_only for x in ["WESEL", "WLSE"]): 
                    target_keyword, kode_ceklis, kategori_nama = "WESEL", "BPBYE1", "WESEL"
                elif any(x in name_only for x in ["AXLE", "COUNTER", "AXL"]): 
                    target_keyword, kode_ceklis, kategori_nama = "AXLE", "BPBYE7", "AXC"
                elif any(x in name_only for x in ["SINYAL", "BLOK", "ZP"]): 
                    target_keyword, kode_ceklis, kategori_nama = "SINYAL", "BPBYE3", "SINYAL"
                elif any(x in name_only for x in ["FIBER OPTIK", "FO", "SERAT OPTIK", "TRANSMISI"]):
                    target_keyword, kode_ceklis, kategori_nama = "SERAT OPTIK", "BPBYE5", "FIBER"

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

                        # 2. PROSES SCANNING MULTI-LINE BERDASARKAN POLA INTERNAL KAI (WSL / AXL / SIN)
                        for line in lines:
                            
                            # ==================== KATEGORI WESEL ====================
                            if target_keyword == "WESEL" and "WSL" in line and ":" in line:
                                right_side = line.split(":")[-1].strip()
                                
                                # 1. Hapus variasi kata jika mereka menempel atau ber spasi
                                right_side = right_side.replace("WESEL ELEKTRIK TERLAYAN SETEMPAT", "")
                                right_side = right_side.replace("WESEL ELEKTRIK", "")
                                right_side = right_side.replace("PENGGERAK WESEL", "")
                                right_side = right_side.replace("WESELPENGGERAK", "") # <-- Kunci untuk error saat ini
                                
                                # 2. Hapus kata mandiri secara agresif untuk membersihkan sisa kata yang menempel
                                right_side = right_side.replace("PENGGERAK", "")
                                right_side = right_side.replace("ELEKTRIK", "")
                                right_side = right_side.replace("WESEL", "").strip()
                                
                                words = right_side.split()
                                if words:
                                    # Pastikan ID diawali huruf W dengan rapi (misal dari "21" menjadi "W21")
                                    aid = words[0] if words[0].startswith("W") else f"W{words[0]}"
                                    loc_id = " ".join(words[1:]) if len(words) > 1 else "LOKASI"
                                    assets_found.append({"id": aid, "loc": loc_id})

                            # ==================== KATEGORI AXLE COUNTER ====================
                            elif target_keyword == "AXLE" and "AXL" in line and ":" in line:
                                right_side = line.split(":")[-1].strip()
                                
                                # Bersihkan variasi teks AXLE COUNTER dan karakter titik/noise
                                right_side = right_side.replace("AXLE.COUNTER.", "").replace("AXLE COUNTER", "")
                                right_side = right_side.replace(".", " ").strip() # Ubah sisa titik menjadi spasi
                                
                                words = right_side.split()
                                if words:
                                    # Logika penanganan ZP
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
                            elif target_keyword == "SERAT OPTIK":
                                # Cari pola "TRA***** :" di mana ***** bisa apa saja (karakter non-spasi)
                                tra_match = re.search(r'TRA\S*\s*:', line)
                                if tra_match:
                                    # Mengambil bagian setelah ':'
                                    right_side = line.split(":")[-1].strip()
                                    
                                    # ID Aset Spesifik: "OTB 1"
                                    aid = "OTB 1" 
                                    
                                    # Lokasi adalah sisa teks setelah "OTB 1"
                                    if aid in right_side:
                                        loc_id_temp = right_side.split(aid, 1)[-1].strip()
                                        loc_id = loc_id_temp if loc_id_temp else "LOKASI"
                                    else:
                                        loc_id = right_side if right_side else "LOKASI"
                                    
                                    assets_found.append({"id": aid, "loc": loc_id})
                                    break # Hanya perlu satu deteksi per file untuk ceklis ini.
                                
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

# ... existing code ...