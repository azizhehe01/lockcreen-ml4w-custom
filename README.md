# ML4W Hyprlock Screen (Layout 16 Adaptation)

Custom lock screen yang modern dan dinamis untuk **Hyprland** (diadaptasi untuk **ML4W Dotfiles**). Menggunakan Python rendering engine untuk meng-generate konfigurasi native `hyprlock` secara otomatis berdasarkan file konfigurasi TOML yang mudah diedit.

---

## ✨ Fitur Utama

- **Canvas Responsive Auto-Scale**: Didesain pada canvas 1920x1080 dan otomatis diskalakan proporsional sesuai resolusi monitor aktif.
- **Dynamic Avatar**: Mendukung foto avatar custom (JPG/PNG dengan auto-crop & thumbnail) atau fallback otomatis ke badge inisial monogram melingkar.
- **Music Player Widget (MPRIS)**:
  - Menampilkan judul lagu, artis, dan pemutar musik aktif via `playerctl`.
  - Menampilkan cover art album Spotify secara dinamis dengan auto-reload.
  - Tombol kontrol interaktif: *Previous*, *Play/Pause*, dan *Next* yang bisa diklik langsung di layar lockscreen.
- **Weather Widget**: Menampilkan cuaca, temperatur, dan ikon cuaca menggunakan Open-Meteo & IP geolocation (atau nama kota manual). Otomatis cache selama 30 menit.
- **Battery Widget**: Indikator persentase baterai real-time dan status pengisian daya (charging).
- **Frosted Blur & Dimming**: Efek blur wallpaper yang halus dan bisa disesuaikan (`blur_passes`, `blur_size`, `brightness`).
- **Flexible Relative Positioning**: Tata letak widget modular menggunakan anchor layar (`top-center`, `center`, dsb) atau relatif terhadap widget lain (`below`, `above`, `left-of`, `right-of`).

---

## 📦 Kebutuhan Sistem (Prerequisites)

Pastikan dependensi berikut sudah terpasang di sistem kamu:

1. **Hyprland & Hyprlock**:
   ```bash
   # Arch Linux:
   sudo pacman -S hyprlock playerctl python-pillow
   
   # Fedora:
   sudo dnf install hyprlock playerctl python3-pillow
   ```
2. **Python 3.11+** (menggunakan modul bawaan `tomllib`).
3. **Font**: **JetBrains Mono**
   - Pastikan font terpasang di sistem (misal `~/.local/share/fonts/` atau melalui package manager).

---

## 📁 Struktur File

```text
~/.config/hypr/lockscreen/
├── assets/                       # Folder gambar / avatar custom
├── hyprlock.ml4w-original.conf   # Backup konfigurasi default ML4W
├── lock                          # Wrapper script peluncur lockscreen
├── render.py                     # Python compiler (TOML -> hyprlock.conf)
├── settings.toml                 # File konfigurasi utama
├── settings.toml.example         # Template konfigurasi contoh
├── test_render.py                # Unit test validasi layout
└── widget.py                     # Script backend helper (cuaca, musik, baterai)
```

> **Catatan penting:** File aktif Hyprlock kamu ada di `~/.config/hypr/hyprlock.conf`. File tersebut merupakan file **hasil generate otomatis** dari `render.py`. Jangan mengedit `hyprlock.conf` langsung karena akan tertimpa saat render ulang.

---

## 🚀 Cara Penggunaan

### 1. Uji Coba Konfigurasi
Sebelum mengunci layar, validasi file konfigurasi kamu:
```bash
python3 ~/.config/hypr/lockscreen/render.py --check
```
Jika valid, generate file konfigurasi ke `hyprlock.conf`:
```bash
python3 ~/.config/hypr/lockscreen/render.py
```

### 2. Menjalankan Lockscreen Secara Manual
Gunakan script wrapper `lock` yang sudah disediakan:
```bash
~/.config/hypr/lockscreen/lock
```
Script ini akan:
1. Memastikan tidak ada proses `hyprlock` yang sedang ganda.
2. Memperbarui wallpaper dan cover album terbaru.
3. Meng-compile konfigurasi dan menjalankan `hyprlock`.

---

## ⚙️ Integrasi dengan Hyprland / ML4W

Agar lockscreen baru ini otomatis aktif saat menekan shortcut atau saat sistem idle:

### 1. Shortcut Keyboard (Hyprland Config)
Cari bind pengunci layar di konfigurasi Hyprland kamu (misal `~/.config/hypr/conf/keybindings.conf`), arahkan ke script `lock`:
```ini
bind = $mainMod CTRL, L, exec, ~/.config/hypr/lockscreen/lock
```

### 2. Auto-Lock Saat Idle (`hypridle.conf`)
Di `~/.config/hypr/hypridle.conf`:
```ini
listener {
    timeout = 300
    on-timeout = ~/.config/hypr/lockscreen/lock
}
```

---

## 🎨 Panduan Kustomisasi (`settings.toml`)

Semua preferensi tampilan diatur melalui file `settings.toml`.

### Mengganti Avatar
- **Pakai foto sendiri**:
  Simpan foto kamu (misal di `~/.config/hypr/lockscreen/assets/avatar.png`), lalu ubah di `settings.toml`:
  ```toml
  [avatar]
  enabled = true
  image = "~/.config/hypr/lockscreen/assets/avatar.png"
  ```
- **Pakai inisial monogram (default)**:
  Kosongkan `image = ""` dan tentukan huruf inisial:
  ```toml
  [avatar]
  enabled = true
  image = ""
  initials = "AZ"
  ```

### Mengatur Widget Cuaca
- **Otomatis mendeteksi lokasi**:
  ```toml
  [weather]
  city = "auto"
  ```
- **Lokasi manual**:
  ```toml
  [weather]
  city = "Jakarta"  # atau kota pilihan kamu
  ```

### Menonaktifkan Widget Tertentu
Setiap widget memiliki opsi `enabled = true/false`.
```toml
[music]
enabled = false  # menyembunyikan widget musik
```
*Tip: Jika widget lain menggunakan widget yang disembunyikan sebagai patokan posisi (anchor), tata letaknya tetap akan terjaga rapi.*

---

## 🧪 Menjalankan Unit Test

Untuk memastikan seluruh parser, layout, dan widget rendering bekerja dengan benar tanpa error:
```bash
python3 ~/.config/hypr/lockscreen/test_render.py
```

---

## 🔄 Cara Restore ke Konfigurasi Awal ML4W

Jika ingin kembali ke konfigurasi standar ML4W kapan saja:
1. Salin kembali file backup:
   ```bash
   cp ~/.config/hypr/lockscreen/hyprlock.ml4w-original.conf ~/.config/hypr/hyprlock.conf
   ```
2. Kembalikan perintah shortcut/lock di konfigurasi `hypridle.conf` atau keybindings ke default ML4W.
