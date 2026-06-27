# radyo.py
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import ctypes
import datetime
import threading
import time
import shutil

# --- BASS.DLL EKOLAYZER VE ENCODING YAPILANDIRMASI (CTYPES) ---
BASS_FX_DX8_PARAMEQ = 7

class BASS_DX8_PARAMEQ(ctypes.Structure):
    _fields_ = [
        ("fCenter", ctypes.c_float),
        ("fBandwidth", ctypes.c_float),
        ("fGain", ctypes.c_float)
    ]

# BASS Gelen Veri Yakalama Callback Tipi (Kayıt İçin)
DOWNLOADPROC = ctypes.WINFUNCTYPE(None, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p)

# Tema Ayarları
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class BasitRadyoModern(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Pencere Ayarları
        self.title("BasitRadyo - Modern Premium Edition")
        self.geometry("900x650")
        self.minsize(800, 500)

        # Değişkenler
        self.stream_handle = 0
        self.is_playing = False
        self.volume = ctypes.c_float(1.0)
        self.last_selected_index = -1
        self.radio_list = []
        self.tree_index_map = {}
        self.fav_urls = set()
        self.favorites_file = "favorites.txt"
        self._last_title = ""

        # Kayıt değişkenleri
        self.is_recording = False
        self.record_file = None
        self.recorded_bytes = 0
        self.temp_filename = "temp_radio_recording.mp3"
        self.download_proc_cap = DOWNLOADPROC(self.download_callback)

        # EQ hafıza
        self.load_eq_settings()
        self.fx_bass_handle = 0
        self.fx_mid_handle = 0
        self.fx_treble_handle = 0

        # Veri yükle
        self.load_favorites_list()
        self.load_playlist()

        # Arayüz
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="📻 BASİT RADYO", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 30))

        self.btn_add = ctk.CTkButton(self.sidebar_frame, text="➕ Radyo Ekle", command=self.open_add_radio_dialog)
        self.btn_add.grid(row=1, column=0, padx=20, pady=10)

        self.btn_timer = ctk.CTkButton(self.sidebar_frame, text="⏳ Kapanma Zamanlayıcı", command=self.open_schedule_exit_dialog)
        self.btn_timer.grid(row=2, column=0, padx=20, pady=10)

        self.btn_shortcuts = ctk.CTkButton(self.sidebar_frame, text="⌨️ Kısayollar", command=self.show_shortcuts)
        self.btn_shortcuts.grid(row=3, column=0, padx=20, pady=10)

        self.btn_about = ctk.CTkButton(self.sidebar_frame, text="ℹ️ Hakkında", command=self.show_about)
        self.btn_about.grid(row=4, column=0, padx=20, pady=10)

        self.btn_eq = ctk.CTkButton(self.sidebar_frame, text="🎛️ Ekolayzer (EQ)", fg_color="#2b2b2b", hover_color="#1f538d", command=self.open_equalizer_dialog)
        self.btn_eq.grid(row=5, column=0, padx=20, pady=10)

        self.lbl_volume = ctk.CTkLabel(self.sidebar_frame, text="Ses Seviyesi: %100", font=ctk.CTkFont(size=12))
        self.lbl_volume.grid(row=7, column=0, padx=20, pady=(10, 0))

        self.slider_volume = ctk.CTkSlider(self.sidebar_frame, from_=0, to=1, command=self.on_volume_slider)
        self.slider_volume.set(1.0)
        self.slider_volume.grid(row=8, column=0, padx=20, pady=(5, 20))

        # Main frame
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        # RDS ekranı
        self.rds_frame = ctk.CTkFrame(self.main_frame, fg_color="#111111", corner_radius=12, border_width=1, border_color="#333333")
        self.rds_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 20))

        self.rds_station_label = ctk.CTkLabel(self.rds_frame, text="Radyo Seçilmedi", font=ctk.CTkFont(size=18, weight="bold"), text_color="#1f538d")
        self.rds_station_label.pack(anchor="w", padx=20, pady=(15, 5))

        self.rds_song_label = ctk.CTkLabel(self.rds_frame, text="🎵 Canlı Yayın Akışı Bekleniyor...", font=ctk.CTkFont(size=14, slant="italic"), text_color="#00ffcc")
        self.rds_song_label.pack(anchor="w", padx=20, pady=(0, 15))

        # Sekme
        self.tab_selector = ctk.CTkSegmentedButton(self.main_frame, values=["Tüm Radyolar", "Favoriler"], command=self.on_tab_changed)
        self.tab_selector.set("Tüm Radyolar")
        self.tab_selector.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 10))

        # Treeview stil
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview",
                             background="#1a1a1a",
                             foreground="#ffffff",
                             fieldbackground="#1a1a1a",
                             rowheight=38,
                             font=("Segoe UI", 11))
        self.style.map("Treeview", background=[("selected", "#1f538d")], foreground=[("selected", "#ffffff")])
        self.style.configure("Treeview.Heading", background="#2d2d2d", foreground="#ffffff", borderwidth=0, font=("Segoe UI", 11, "bold"))
        self.style.map("Treeview.Heading", background=[("active", "#3d3d3d")])

        # Table frame
        self.table_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.table_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=0)
        self.table_frame.grid_columnconfigure(0, weight=1)
        self.table_frame.grid_rowconfigure(0, weight=1)

        self.scrollbar = ctk.CTkScrollbar(self.table_frame)
        self.scrollbar.grid(row=0, column=1, sticky="ns")

        self.tree = ttk.Treeview(self.table_frame, columns=("name", "fav"), show="headings", selectmode="browse", yscrollcommand=self.scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.configure(command=self.tree.yview)

        self.tree.heading("name", text="🎵 Radyo İstasyonu", anchor="w")
        self.tree.heading("fav", text="❤️ Durum", anchor="center")
        self.tree.column("name", width=420, stretch=True, anchor="w")
        self.tree.column("fav", width=110, minwidth=80, stretch=False, anchor="center")

        self.tree.bind("<Double-1>", self.on_tree_double_click)

        # Action buttons
        self.action_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.action_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(15, 0))

        self.btn_play_selected = ctk.CTkButton(self.action_frame, text="▶️ Oynat / Durdur", fg_color="#1f538d", font=ctk.CTkFont(weight="bold"), command=self.play_selected)
        self.btn_play_selected.pack(side="left", padx=(0, 5), expand=True, fill="x")

        self.btn_record = ctk.CTkButton(self.action_frame, text="🔴 Kaydı Başlat", fg_color="#d32f2f", hover_color="#b71c1c", command=self.toggle_recording)
        self.btn_record.pack(side="left", padx=5)

        self.btn_fav_selected = ctk.CTkButton(self.action_frame, text="❤️ Favori", fg_color="#2b2b2b", hover_color="#e91e63", width=90, command=self.toggle_favorite_selected)
        self.btn_fav_selected.pack(side="left", padx=5)

        self.btn_edit_selected = ctk.CTkButton(self.action_frame, text="✏️ Düzenle", fg_color="#2b2b2b", width=90, command=self.edit_selected)
        self.btn_edit_selected.pack(side="left", padx=5)

        self.btn_delete_selected = ctk.CTkButton(self.action_frame, text="🗑️ Sil", fg_color="#2b2b2b", hover_color="#f44336", width=90, command=self.delete_selected)
        self.btn_delete_selected.pack(side="left", padx=5)

        # Kısayollar
        self.bind("<space>", self.on_space_key)
        self.bind("<Right>", self.on_right_key)
        self.bind("<Left>", self.on_left_key)

        # İlk tablo
        self.update_radio_display()

        # BASS DLL yolları
        self.BASS_DLL_PATH = os.path.join("bass", "bass.dll")
        self.BASSHLS_DLL_PATH = os.path.join("bass", "basshls.dll")

        try:
            self.bass = ctypes.WinDLL(self.BASS_DLL_PATH)
            try:
                plugin = self.bass.BASS_PluginLoad(self.BASSHLS_DLL_PATH.encode(), 0)
                if not plugin:
                    print("BASS_PluginLoad hatası:", self.bass.BASS_ErrorGetCode())
                else:
                    print("BASS plugin yüklendi:", plugin)
            except Exception as e:
                print("BASS_PluginLoad çağrılırken hata:", e)

            try:
                init_ok = self.bass.BASS_Init(-1, 44100, 0, 0, 0)
                if not init_ok:
                    print("BASS_Init hatası:", self.bass.BASS_ErrorGetCode())
                else:
                    print("BASS_Init başarılı")
            except Exception as e:
                print("BASS_Init çağrılırken hata:", e)

            try:
                self.bass.BASS_ChannelGetTags.restype = ctypes.c_char_p
            except Exception as e:
                print("restype ayarlanırken hata:", e)

        except Exception as e:
            print("BASS Sürüceler yüklenirken hata oluştu!", e)

        # RDS döngüsü başlat
        threading.Thread(target=self.update_rds_loop, daemon=True).start()

    # --- EQ hafıza ---
    def load_eq_settings(self):
        self.eq_bass_val = 0.0
        self.eq_mid_val = 0.0
        self.eq_treble_val = 0.0
        if os.path.exists("eq_settings.txt"):
            try:
                with open("eq_settings.txt", "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        b, m, t = content.split(",")
                        self.eq_bass_val = float(b)
                        self.eq_mid_val = float(m)
                        self.eq_treble_val = float(t)
            except Exception as e:
                print("EQ Hafıza dosyası okunurken hata oluştu, varsayılana dönüldü:", e)

    def save_eq_settings(self):
        try:
            with open("eq_settings.txt", "w", encoding="utf-8") as f:
                f.write(f"{self.eq_bass_val},{self.eq_mid_val},{self.eq_treble_val}")
        except Exception as e:
            print("EQ Hafıza dosyasına yazma hatası:", e)

    # --- Favoriler / playlist ---
    def load_favorites_list(self):
        if os.path.exists(self.favorites_file):
            with open(self.favorites_file, "r", encoding="utf-8") as f:
                self.fav_urls = set(line.strip() for line in f if line.strip())

    def save_favorites_list(self):
        with open(self.favorites_file, "w", encoding="utf-8") as f:
            for url in self.fav_urls:
                f.write(f"{url}\n")

    def load_playlist(self):
        try:
            self.radio_list = []
            if os.path.exists("playlist.m3u"):
                try:
                    with open("playlist.m3u", "r", encoding="utf-8") as file:
                        lines = file.readlines()
                except UnicodeDecodeError:
                    with open("playlist.m3u", "r", encoding="cp1254") as file:
                        lines = file.readlines()

                name = "Bilinmeyen Radyo"
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("#EXTINF"):
                        if "," in line:
                            name = line.split(",", 1)[1].strip()
                    elif line.startswith("#"):
                        continue
                    else:
                        url = line
                        is_fav = url in self.fav_urls
                        self.radio_list.append({"name": name, "url": url, "favorite": is_fav})
            self.radio_list.sort(key=lambda x: x["name"])
        except Exception as e:
            print("Playlist yüklenirken hata:", e)

    def save_playlist(self):
        try:
            with open("playlist.m3u", "w", encoding="utf-8") as file:
                for item in self.radio_list:
                    file.write(f"#EXTINF:-1,{item['name']}\n{item['url']}\n")
        except Exception as e:
            print("Playlist kaydedilirken hata:", e)

    # --- UI güncelleme ---
    def update_radio_display(self):
        self.tree.delete(*self.tree.get_children())
        self.tree_index_map = {}
        current_tab = self.tab_selector.get()
        for index, item in enumerate(self.radio_list):
            if current_tab == "Favoriler" and not item["favorite"]:
                continue
            fav_status = "❤️ Favoride" if item["favorite"] else "🤍 Standart"
            display_name = item["name"]
            if self.is_playing and self.last_selected_index == index:
                display_name = f"🔊 {display_name}"
            item_id = self.tree.insert("", "end", values=(display_name, fav_status))
            self.tree_index_map[item_id] = index
            if self.is_playing and self.last_selected_index == index:
                self.tree.selection_set(item_id)
                self.tree.see(item_id)

    def on_tab_changed(self, tab_name):
        self.update_radio_display()

    def get_selected_radio_index(self):
        selected_item = self.tree.selection()
        if selected_item:
            return self.tree_index_map.get(selected_item[0])
        return None

    # --- Oynatma ---
    def on_tree_double_click(self, event):
        idx = self.get_selected_radio_index()
        if idx is not None:
            self.toggle_play(idx)

    def play_selected(self):
        idx = self.get_selected_radio_index()
        if idx is not None:
            self.toggle_play(idx)
        elif self.last_selected_index != -1:
            self.toggle_play(self.last_selected_index)

    def toggle_play(self, index):
        item = self.radio_list[index]
        if self.stream_handle != 0 and self.is_playing and self.last_selected_index == index:
            self.is_playing = False
            if self.is_recording:
                self.stop_recording_silent(delete_temp=True)
            try:
                self.bass.BASS_ChannelPause(self.stream_handle)
            except:
                pass
            self.rds_station_label.configure(text="Yayın Durduruldu")
            self.rds_song_label.configure(text="🎵 Müzik kapatıldı.")
            self.btn_play_selected.configure(text="▶️ Oynat", fg_color="#1f538d")
            self.update_radio_display()
        else:
            if self.is_recording:
                self.stop_recording_silent(delete_temp=True)
            if self.stream_handle != 0:
                try:
                    self.bass.BASS_ChannelStop(self.stream_handle)
                except:
                    pass
            self.rds_station_label.configure(text=f"📡 Bağlanıyor: {item['name']}...")
            self.rds_song_label.configure(text="🎵 Yayın sunucusuna istek gönderildi, bekleniyor...")
            self.btn_play_selected.configure(text="⏸️ Durdur", fg_color="#d32f2f")
            threading.Thread(target=self.async_play, args=(item["url"], index), daemon=True).start()

    def async_play(self, url, index):
        try:
            handle = self.bass.BASS_StreamCreateURL(url.encode(), 0, 0, self.download_proc_cap, 0)
        except Exception as e:
            print("BASS_StreamCreateURL hata:", e)
            handle = 0

        if handle != 0:
            self.stream_handle = handle
            self.is_playing = True
            try:
                self.bass.BASS_ChannelPlay(self.stream_handle, False)
            except:
                pass
            self.set_volume(self.volume.value)
            self.last_selected_index = index
            self._last_title = ""
            try:
                self.fx_bass_handle = self.bass.BASS_ChannelSetFX(self.stream_handle, BASS_FX_DX8_PARAMEQ, 0)
                self.fx_mid_handle = self.bass.BASS_ChannelSetFX(self.stream_handle, BASS_FX_DX8_PARAMEQ, 1)
                self.fx_treble_handle = self.bass.BASS_ChannelSetFX(self.stream_handle, BASS_FX_DX8_PARAMEQ, 2)
                self.update_eq_dsp_values()
            except Exception as e:
                print("FX setleme hatası:", e)
            self.after(0, lambda: self.rds_station_label.configure(text=f"📻 CANLI: {self.radio_list[index]['name']}"))
            self.after(0, lambda: self.rds_song_label.configure(text="🎵 Canlı akış aktif (RDS bekleniyor)..."))
        else:
            try:
                err = self.bass.BASS_ErrorGetCode()
            except:
                err = "?"
            self.is_playing = False
            self.after(0, lambda: self.rds_station_label.configure(text="❌ Bağlantı Başarısız"))
            self.after(0, lambda: self.rds_song_label.configure(text=f"Yayın çevrimdışı veya link kırık. (Hata Kodu: {err})"))
            self.after(0, lambda: self.btn_play_selected.configure(text="▶️ Oynat", fg_color="#1f538d"))
        self.after(0, self.update_radio_display)

    # --- Kayıt ---
    def download_callback(self, buffer, length, user):
        if self.is_recording and self.record_file and buffer and length > 0:
            try:
                data = ctypes.string_at(buffer, length)
                self.record_file.write(data)
                self.recorded_bytes += length
            except Exception as e:
                print("Kayıt dosyasına yazma hatası:", e)

    def toggle_recording(self):
        if not self.is_playing or self.stream_handle == 0:
            messagebox.showwarning("Kayıt Başlatılamadı", "Kayıt yapabilmek için önce canlı bir radyo yayını açmalısınız şef!")
            return

        if self.is_recording:
            self.is_recording = False
            if self.record_file:
                try:
                    self.record_file.close()
                except:
                    pass
                self.record_file = None
            self.btn_record.configure(text="🔴 Kaydı Başlat", fg_color="#2b2b2b")
            current_radio = self.radio_list[self.last_selected_index]
            clean_name = "".join(c for c in current_radio["name"] if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            suggested_filename = f"RadyoKayit_{clean_name}_{timestamp}.mp3"
            target_path = filedialog.asksaveasfilename(
                title="Radyo Kaydını Nereye Kaydetmek İstersiniz şef?",
                initialfile=suggested_filename,
                defaultextension=".mp3",
                filetypes=[("MP3 Müzik Dosyası", "*.mp3"), ("Tüm Dosyalar", "*.*")]
            )
            if target_path:
                try:
                    if os.path.exists(self.temp_filename):
                        shutil.move(self.temp_filename, target_path)
                        messagebox.showinfo("Kayıt Başarılı", f"Ses kaydı başarıyla diske yazıldı!\n\nKonum: {target_path}")
                except Exception as e:
                    messagebox.showerror("Hata", f"Dosya hedefe taşınırken hata oluştu: {e}")
            else:
                try:
                    if os.path.exists(self.temp_filename):
                        os.rename(self.temp_filename, suggested_filename)
                        messagebox.showinfo("Kayıt İptal Edildi", f"Seçim yapmadınız. Kaydınız silinmesin diye uygulama klasörüne kaydedildi:\n{suggested_filename}")
                except:
                    pass
        else:
            try:
                if os.path.exists(self.temp_filename):
                    os.remove(self.temp_filename)
            except:
                pass
            try:
                self.record_file = open(self.temp_filename, "wb")
                self.recorded_bytes = 0
                self.is_recording = True
                self.btn_record.configure(text="⏹️ Kaydı Durdur (0 KB)", fg_color="#d32f2f")
            except Exception as e:
                messagebox.showerror("Hata", f"Geçici kayıt dosyası oluşturulamadı: {e}")

    def stop_recording_silent(self, delete_temp=True):
        self.is_recording = False
        if self.record_file:
            try:
                self.record_file.close()
            except:
                pass
            self.record_file = None
        if delete_temp and os.path.exists(self.temp_filename):
            try:
                os.remove(self.temp_filename)
            except:
                pass
        if hasattr(self, 'btn_record'):
            self.btn_record.configure(text="🔴 Kaydı Başlat", fg_color="#2b2b2b")

    # --- EQ uygulama ---
    def update_eq_dsp_values(self):
        if not self.stream_handle or not self.is_playing:
            return
        if self.fx_bass_handle:
            p_bass = BASS_DX8_PARAMEQ(100.0, 18.0, float(self.eq_bass_val))
            try:
                self.bass.BASS_FXSetParameters(self.fx_bass_handle, ctypes.byref(p_bass))
            except:
                pass
        if self.fx_mid_handle:
            p_mid = BASS_DX8_PARAMEQ(1000.0, 18.0, float(self.eq_mid_val))
            try:
                self.bass.BASS_FXSetParameters(self.fx_mid_handle, ctypes.byref(p_mid))
            except:
                pass
        if self.fx_treble_handle:
            p_treble = BASS_DX8_PARAMEQ(8000.0, 18.0, float(self.eq_treble_val))
            try:
                self.bass.BASS_FXSetParameters(self.fx_treble_handle, ctypes.byref(p_treble))
            except:
                pass

    # --- Favori toggle ---
    def toggle_favorite_selected(self):
        idx = self.get_selected_radio_index()
        if idx is None:
            return
        url = self.radio_list[idx]["url"]
        if url in self.fav_urls:
            self.fav_urls.remove(url)
            self.radio_list[idx]["favorite"] = False
        else:
            self.fav_urls.add(url)
            self.radio_list[idx]["favorite"] = True
        self.save_favorites_list()
        self.update_radio_display()

    # --- Gelişmiş RDS döngüsü (tek, düzgün blok) ---
    def update_rds_loop(self):
        """
        Gelişmiş RDS/metadata döngüsü:
        - Birden fazla tag_type dener
        - HTTP header (HTTP/1.1 200 OK) durumunu parse eder (icy-* header'ları)
        - Eğer header/StreamTitle yoksa, radyo URL'sini HTTP ile çekip M3U8 içindeki #EXTINF satırlarını kontrol eder
        - Debug çıktısı verir
        """
        import urllib.request
        import urllib.error

        while True:
            try:
                if hasattr(self, 'bass') and self.stream_handle != 0 and self.is_playing:
                    found = False
                    title = ""

                    # 1) BASS tag tiplerini dene
                    for tag_type in (1, 0, 2, 3, 4, 5):
                        try:
                            tags = self.bass.BASS_ChannelGetTags(self.stream_handle, tag_type)
                        except Exception as e:
                            print(f"DEBUG: BASS_ChannelGetTags hata (type {tag_type}):", e)
                            tags = None

                        if not tags:
                            continue

                        try:
                            debug_str = tags.decode('utf-8', errors='ignore')
                        except Exception:
                            debug_str = str(tags)
                        print(f"DEBUG: tag_type={tag_type} -> {debug_str}")

                        # HTTP/ICY header'ları varsa parse et
                        if debug_str.strip().upper().startswith("HTTP/1.1") or debug_str.strip().upper().startswith("HTTP/1.0") or debug_str.strip().upper().startswith("ICY/1.0"):
                            lines = [ln.strip() for ln in debug_str.splitlines() if ln.strip()]
                            headers = {}
                            for ln in lines:
                                if ":" in ln:
                                    k, v = ln.split(":", 1)
                                    headers[k.strip().lower()] = v.strip()
                            for key in ("icy-name", "icy-description", "icy-br", "icy-url", "server"):
                                if key in headers and headers[key]:
                                    candidate = headers[key]
                                    if len(candidate) > 2:
                                        title = candidate
                                        found = True
                                        break
                            if not found:
                                for key in ("name", "title"):
                                    if key in headers and headers[key]:
                                        title = headers[key]
                                        found = True
                                        break

                        # StreamTitle formatı
                        if not found and "StreamTitle='" in debug_str:
                            try:
                                title = debug_str.split("StreamTitle='")[1].split("';")[0].strip()
                            except:
                                title = debug_str.strip()
                            found = True

                        # Alternatif anahtarlar
                        if not found and ("StreamTitle:" in debug_str or "StreamTitle=" in debug_str):
                            parts = debug_str.replace("StreamTitle=", "StreamTitle:").split("StreamTitle:")
                            if len(parts) > 1:
                                title = parts[1].splitlines()[0].strip()
                                found = True

                        # Doğrudan tek satır title
                        if not found:
                            candidate = debug_str.strip()
                            if 3 < len(candidate) < 300:
                                title = candidate
                                found = True

                        if found:
                            break

                    # 2) Eğer BASS ile bulunamadıysa, playlist/m3u8 içeriğini HTTP ile kontrol et
                    if not found:
                        try:
                            url = None
                            if 0 <= self.last_selected_index < len(self.radio_list):
                                url = self.radio_list[self.last_selected_index].get("url")
                            if not url and self.radio_list:
                                url = self.radio_list[0].get("url")
                            if url:
                                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Icy-MetaData": "1"})
                                with urllib.request.urlopen(req, timeout=5) as resp:
                                    hdrs = {k.lower(): v for k, v in resp.getheaders()}
                                    for key in ("icy-name", "icy-description", "icy-br", "icy-url", "server"):
                                        if key in hdrs and hdrs[key]:
                                            candidate = hdrs[key]
                                            if len(candidate) > 2:
                                                title = candidate
                                                found = True
                                                break
                                    content_type = hdrs.get("content-type", "")
                                    body = b""
                                    try:
                                        body = resp.read(4096)
                                    except Exception:
                                        body = b""
                                    text = ""
                                    try:
                                        text = body.decode("utf-8", errors="ignore")
                                    except Exception:
                                        text = str(body)
                                    if not found and ("#EXTINF" in text or ".m3u8" in content_type.lower()):
                                        for line in text.splitlines():
                                            line = line.strip()
                                            if line.upper().startswith("#EXTINF"):
                                                if "," in line:
                                                    candidate = line.split(",", 1)[1].strip()
                                                    if candidate:
                                                        title = candidate
                                                        found = True
                                                        break
                                    if not found:
                                        candidate = text.strip()
                                        if 3 < len(candidate) < 300:
                                            title = candidate.splitlines()[0].strip()
                                            found = True
                        except urllib.error.HTTPError as he:
                            print("DEBUG: HTTPError metadata fetch:", he)
                        except urllib.error.URLError as ue:
                            print("DEBUG: URLError metadata fetch:", ue)
                        except Exception as e:
                            print("DEBUG: metadata fetch hata:", e)

                    # UI'ya yaz
                    if found and title and title != self._last_title:
                        self._last_title = title
                        self.after(0, lambda t=title: self.rds_song_label.configure(text=f"🎵 {t}"))

                # Kayıt butonu güncellemesi
                if self.is_recording:
                    kb_size = self.recorded_bytes // 1024
                    self.after(0, lambda k=kb_size: self.btn_record.configure(text=f"⏹️ Durdur ({k} KB)"))
            except Exception as e:
                print("RDS döngüsü hata:", e)
            time.sleep(1.5)

    # --- Ses kontrol ---
    def on_volume_slider(self, value):
        self.volume.value = float(value)
        self.set_volume(self.volume.value)
        self.lbl_volume.configure(text=f"Ses Seviyesi: %{int(self.volume.value * 100)}")

    def set_volume(self, volume):
        if hasattr(self, 'bass') and self.stream_handle:
            try:
                self.bass.BASS_ChannelSetAttribute(self.stream_handle, 2, ctypes.c_float(volume))
            except:
                pass

    # --- Kısayollar ---
    def on_space_key(self, event):
        self.play_selected()

    def on_right_key(self, event):
        new_vol = min(1.0, self.slider_volume.get() + 0.05)
        self.slider_volume.set(new_vol)
        self.on_volume_slider(new_vol)

    def on_left_key(self, event):
        new_vol = max(0.0, self.slider_volume.get() - 0.05)
        self.slider_volume.set(new_vol)
        self.on_volume_slider(new_vol)

    # --- Yardımcı pencereler ---
    def create_safe_toplevel(self, title, geometry):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry(geometry)
        dialog.resizable(False, False)
        dialog.configure(bg="#1a1a1a")
        dialog.transient(self)
        dialog.grab_set()
        container = ctk.CTkFrame(dialog, fg_color="#1a1a1a", corner_radius=0)
        container.pack(fill="both", expand=True)
        return dialog, container

    def open_equalizer_dialog(self):
        dialog, frame = self.create_safe_toplevel("🎛️ Premium Canlı Ekolayzer", "450x600")
        ctk.CTkLabel(frame, text="Frekans Kazanç Ayarları (-15dB / +15dB)",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#00ffcc").pack(pady=(15, 10))
        sliders_frame = ctk.CTkFrame(frame, fg_color="transparent")
        sliders_frame.pack(fill="both", expand=True, padx=20)
        sliders_frame.columnconfigure(0, weight=1)
        sliders_frame.columnconfigure(1, weight=1)
        sliders_frame.columnconfigure(2, weight=1)

        b_frame = ctk.CTkFrame(sliders_frame, fg_color="transparent")
        b_frame.grid(row=0, column=0, sticky="nsew")
        lbl_b_val = ctk.CTkLabel(b_frame, text=f"{int(self.eq_bass_val)} dB", text_color="white")
        lbl_b_val.pack()

        def on_bass_scroll(val):
            self.eq_bass_val = float(val)
            lbl_b_val.configure(text=f"{int(self.eq_bass_val)} dB")
            self.update_eq_dsp_values()
            self.save_eq_settings()

        sl_bass = ctk.CTkSlider(b_frame, from_=-15, to=15, orientation="vertical", command=on_bass_scroll)
        sl_bass.set(self.eq_bass_val)
        sl_bass.pack(pady=5, expand=True, fill="y")
        ctk.CTkLabel(b_frame, text="⚡ BAS\n(100 Hz)", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=5)

        m_frame = ctk.CTkFrame(sliders_frame, fg_color="transparent")
        m_frame.grid(row=0, column=1, sticky="nsew")
        lbl_m_val = ctk.CTkLabel(m_frame, text=f"{int(self.eq_mid_val)} dB", text_color="white")
        lbl_m_val.pack()

        def on_mid_scroll(val):
            self.eq_mid_val = float(val)
            lbl_m_val.configure(text=f"{int(self.eq_mid_val)} dB")
            self.update_eq_dsp_values()
            self.save_eq_settings()

        sl_mid = ctk.CTkSlider(m_frame, from_=-15, to=15, orientation="vertical", command=on_mid_scroll)
        sl_mid.set(self.eq_mid_val)
        sl_mid.pack(pady=5, expand=True, fill="y")
        ctk.CTkLabel(m_frame, text="🗣️ MID\n(1 kHz)", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=5)

        t_frame = ctk.CTkFrame(sliders_frame, fg_color="transparent")
        t_frame.grid(row=0, column=2, sticky="nsew")
        lbl_t_val = ctk.CTkLabel(t_frame, text=f"{int(self.eq_treble_val)} dB", text_color="white")
        lbl_t_val.pack()

        def on_treble_scroll(val):
            self.eq_treble_val = float(val)
            lbl_t_val.configure(text=f"{int(self.eq_treble_val)} dB")
            self.update_eq_dsp_values()
            self.save_eq_settings()

        sl_treble = ctk.CTkSlider(t_frame, from_=-15, to=15, orientation="vertical", command=on_treble_scroll)
        sl_treble.set(self.eq_treble_val)
        sl_treble.pack(pady=5, expand=True, fill="y")
        ctk.CTkLabel(t_frame, text="🎼 TİZ\n(8 kHz)", font=ctk.CTkFont(size=11, weight="bold")).pack(pady=5)

        def reset_to_flat():
            sl_bass.set(0); on_bass_scroll(0)
            sl_mid.set(0); on_mid_scroll(0)
            sl_treble.set(0); on_treble_scroll(0)
            self.save_eq_settings()

        ctk.CTkButton(frame, text="Ayarları Sıfırla (Flat)", fg_color="#2b2b2b", hover_color="#d32f2f", width=160, command=reset_to_flat).pack(pady=(10, 15))

    def open_add_radio_dialog(self):
        dialog, frame = self.create_safe_toplevel("Yeni Radyo Ekle", "400x250")
        ctk.CTkLabel(frame, text="Radyo Adı:", text_color="white").pack(pady=(15, 2))
        entry_name = ctk.CTkEntry(frame, width=280, fg_color="#2b2b2b", text_color="white")
        entry_name.pack(pady=2)
        ctk.CTkLabel(frame, text="Yayın URL adresi (Stream URL):", text_color="white").pack(pady=(10, 2))
        entry_url = ctk.CTkEntry(frame, width=280, fg_color="#2b2b2b", text_color="white")
        entry_url.pack(pady=2)

        def save():
            name = entry_name.get().strip()
            url = entry_url.get().strip()
            if name and url:
                is_fav = url in self.fav_urls
                self.radio_list.append({"name": name, "url": url, "favorite": is_fav})
                self.save_playlist()
                self.update_radio_display()
                dialog.destroy()
            else:
                messagebox.showwarning("Eksik Bilgi", "Lütfen radyo adı ve URL girin.")

        ctk.CTkButton(frame, text="Kaydet", command=save).pack(pady=15)

    # Placeholder fonksiyonlar
    def open_schedule_exit_dialog(self): pass
    def show_shortcuts(self): pass
    def show_about(self): pass
    def edit_selected(self): pass
    def delete_selected(self): pass

if __name__ == "__main__":
    app = BasitRadyoModern()
    app.mainloop()
