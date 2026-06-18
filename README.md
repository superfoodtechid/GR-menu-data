# 🍽️ Grab Menu Data — Scraper & Laporan Menu GrabFood

Pipeline otomatis untuk mengunduh dan mengolah **data menu** (item & modifier) dari portal **GrabFood Merchant**, dijalankan melalui satu CLI terpadu dengan dukungan tiga tipe struktur akun.

---

## 🆕 Pembaruan Terbaru (Juni 2026)

- **Dukungan 3 Tipe Portal Grab**: Selain akun normal, kini mendukung akun bertipe **Menu Groups** (contoh: AGSA – Ayam Geprek Suroboyo) dan **Catalog Stores** (contoh: Roti Bakar 41) yang memiliki banyak merchant ID dalam satu portal.
- **Auto-Deteksi Tipe Akun**: Scraper secara otomatis mendeteksi tipe akun melalui fallback chain: `merchant-selector` → `menu-groups API` → `catalog-stores API`.
- **Store ID Matching**: Pencocokan item & modifier menu kini memprioritaskan `Store ID` (bukan hanya nama), sehingga file Excel untuk cabang multi-outlet tidak lagi kosong.
- **Struktur Subfolder per Outlet**: Hasil laporan disimpan dalam subfolder tersendiri per outlet di `laporan/menu/<NamaOutlet>/` — baik lokal maupun di Google Drive.
- **Upload Otomatis ke Google Drive**: File laporan per outlet dikirim otomatis ke subfolder Google Drive yang sesuai via Google Apps Script. File master **tidak** diunggah ke Drive.
- **Bersihkan Data Lokal**: Menu baru di CLI untuk menghapus semua file laporan lokal sekaligus.

---

## 📁 Struktur Proyek

```
Grab Menu Data/
├── cli.py                    # Entry point utama (wizard interaktif)
├── config.json               # Konfigurasi global (headless, concurrency)
├── pyproject.toml            # Definisi dependensi (dikelola uv)
├── start.bat                 # Script setup & run (Windows)
├── start.sh                  # Script setup & run (Linux/macOS)
├── .env                      # Konfigurasi Google Drive (tidak di-commit)
├── google_apps_script.gs     # Apps Script untuk upload ke Google Drive
├── upload_to_gdrive.py       # Modul upload file via Google Apps Script
├── grab/
│   ├── grab_api_scraper.py   # Logika scraping API Grab (Playwright + Cookie)
│   ├── main.py               # Pipeline multi-portal Grab Menu
│   └── result.py             # Kalkulasi & format hasil
├── laporan/
│   └── menu/                 # Output file Excel menu (subfolder per outlet)
└── scratch/                  # Script debug & diagnostik (tidak di-commit)
```

---

## ⚙️ Prasyarat

| Kebutuhan | Versi Minimum |
|---|---|
| Python | ≥ 3.12 |
| [uv](https://docs.astral.sh/uv/) | terbaru |
| Google Chrome | terbaru |

---

## 🔧 Instalasi

### Windows

```bat
start.bat
```

### Linux / macOS

```bash
bash start.sh
```

### Manual

```bash
# Install uv jika belum ada
pip install uv

# Sync dependensi virtual environment
uv sync

# Install browser Chromium untuk Playwright
uv run python -m playwright install chromium

# Jalankan CLI
uv run python cli.py
```

---

## 🗂️ Konfigurasi

### `config.json`

```json
{
  "headless_grab": true,
  "max_concurrency": 3,
  "batch_size": 5,
  "batch_delay": 5
}
```

| Key | Tipe | Default | Keterangan |
|---|---|---|---|
| `headless_grab` | bool | `true` | Jalankan browser Grab tanpa GUI |
| `max_concurrency` | int | `3` | Jumlah akun yang diproses paralel |
| `batch_size` | int | `5` | Jumlah akun per batch |
| `batch_delay` | int | `5` | Jeda antar batch (detik) |

### `.env` — Konfigurasi Google Drive (opsional)

```env
# URL Web App Google Apps Script (deploy sebagai "Anyone can access")
GDRIVE_APPSCRIPT_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec

# ID folder Google Drive tujuan upload (folder induk)
GDRIVE_FOLDER_ID=your_folder_id_here
```

> Jika `GDRIVE_APPSCRIPT_URL` tidak diisi, proses upload akan dilewati secara otomatis.

---

## 🚀 Cara Penggunaan

### Mode Interaktif (Direkomendasikan)

```bash
uv run python cli.py
```

Wizard akan menampilkan menu:

```
=================================================================
★                     GET OUTLET DATA GRAB                    ★
=================================================================

  Pilih cakupan outlet:
    [1] Pilih semua outlet
    [2] Pilih custom (Filter spesifik)
    [3] Bersihkan data laporan lokal
    [4] Keluar
```

### Mode CLI (Non-Interaktif)

```bash
# Semua outlet
uv run python grab/main.py

# Filter outlet tertentu
uv run python grab/main.py --outlet "Nama Outlet"

# Filter outlet + cabang
uv run python grab/main.py --outlet "Nama Outlet" --branch "Nama Cabang"

# Filter berdasarkan username akun
uv run python grab/main.py --user "username@email.com"

# Override direktori output
uv run python grab/main.py --output-dir "path/ke/direktori"
```

---

## 🏗️ Tipe Struktur Akun yang Didukung

Scraper mendukung **3 tipe struktur akun** GrabFood Merchant secara otomatis:

| # | Tipe | Contoh | Cara Deteksi | Endpoint Menu |
|---|---|---|---|---|
| 1 | **Normal** | Holans, dll | `merchant-selector` langsung punya `stores[]` | `/food/merchant/v2/menu` |
| 2 | **Menu Groups** | AGSA – Geprek/Cinara/Hauchek | Group ID `IDMG*` tanpa stores → `menu-groups` API | `/food/merchant/v2/menu-groups/menu?menuGroupID=...` |
| 3 | **Catalog Stores** | Roti Bakar 41 | Tidak ada stores → `catalog-stores` API | `/food/merchant/v2/menu` dengan `merchantid` |

### Fallback Chain Otomatis

```
merchant-selector stores[]
       ↓ (kosong)
menu-groups API  →  /food/merchant/v1/menu-groups
       ↓ (kosong)
catalog-stores API  →  /foodtroy/v1/ID/merchant-groups/catalog-stores
       ↓ (kosong)
group_id sebagai fallback terakhir
```

---

## 🔄 Alur Pipeline

```
[Google Sheets]       →  Ambil daftar outlet, Store ID & kredensial
       ↓
[Auto-Deteksi Tipe]   →  Normal / Menu Groups / Catalog Stores
       ↓
[Playwright / Cookie] →  Login & fetch menu via API Grab
       ↓
[Store ID Matching]   →  Cocokkan item & modifier ke portal yang tepat
       ↓
[Excel per Outlet]    →  laporan/menu/<NamaOutlet>/<NamaOutlet>_menu_item.xlsx
                          laporan/menu/<NamaOutlet>/<NamaOutlet>_menu_modifier.xlsx
       ↓
[Master Merge]        →  laporan/menu/0Master_menu_item.xlsx   (lokal saja)
                          laporan/menu/0Master_menu_modifier.xlsx (lokal saja)
       ↓
[Google Drive Upload] →  Upload file per outlet ke subfolder masing-masing
                          (file master TIDAK diunggah ke Drive)
```

---

## 📊 Output Laporan

### Struktur Lokal

```
laporan/menu/
├── 0Master_menu_item.xlsx          # Gabungan semua item (lokal saja, tidak ke Drive)
├── 0Master_menu_modifier.xlsx      # Gabungan semua modifier (lokal saja, tidak ke Drive)
├── NamaOutlet1/
│   ├── NamaOutlet1_menu_item.xlsx
│   └── NamaOutlet1_menu_modifier.xlsx
├── NamaOutlet2_CabangA/
│   ├── NamaOutlet2_CabangA_menu_item.xlsx
│   └── NamaOutlet2_CabangA_menu_modifier.xlsx
└── ...
```

### Struktur Google Drive

```
[GDRIVE_FOLDER_ID]/                 ← folder induk
├── NamaOutlet1/                    ← subfolder dibuat otomatis
│   ├── NamaOutlet1_menu_item.xlsx
│   └── NamaOutlet1_menu_modifier.xlsx
├── NamaOutlet2_CabangA/
│   ├── NamaOutlet2_CabangA_menu_item.xlsx
│   └── NamaOutlet2_CabangA_menu_modifier.xlsx
└── ...
```

> File master **tidak** diunggah ke Google Drive — hanya tersedia secara lokal.

### Kolom File Item (`*_menu_item.xlsx`)

| Kolom | Keterangan |
|---|---|
| `Link outlet` | URL GrabFood outlet |
| `Nama panjang` | Nama outlet (dari spreadsheet) |
| `Store ID` | ID merchant Grab |
| `Nama kategori` | Kategori menu |
| `Nama item` | Nama item menu |
| `Jumlah terjual` | Kuantitas terjual |
| `Jumlah modifier group` | Jumlah grup modifier pada item |
| `Jumlah modifier` | Total modifier pada item |
| `Deskripsi item` | Deskripsi menu |
| `Harga item sebelum promo` | Harga normal |
| `Harga item setelah promo` | Harga setelah diskon |
| `Nominal atau persentase promo` | Selisih harga promo |
| `Ketersediaan item` | `Available` / `Sold Out` |
| `Link foto` | URL foto menu |

### Kolom File Modifier (`*_menu_modifier.xlsx`)

| Kolom | Keterangan |
|---|---|
| `Link outlet` | URL GrabFood outlet |
| `Nama panjang` | Nama outlet |
| `Store ID` | ID merchant Grab |
| `Nama item` | Nama item induk |
| `Nama modifier group` | Nama grup modifier |
| `Nama modifier` | Nama opsi modifier |
| `Tipe modifier` | `SINGLE` / `MULTIPLE` |
| `Minimal` | Minimum pilihan |
| `Maksimal` | Maksimum pilihan |
| `Harga modifier` | Harga tambahan modifier |
| `Ketersediaan modifier` | `Available` / `Sold Out` |

---

## ☁️ Upload ke Google Drive

### Setup Google Apps Script

1. Buka [script.google.com](https://script.google.com) → buat project baru
2. Salin isi file `google_apps_script.gs` ke editor Apps Script
3. Klik **Deploy** → **New Deployment** → pilih tipe **Web App**
4. Atur: *Execute as* = **Me**, *Who has access* = **Anyone**
5. Salin URL deployment → isi ke `.env` sebagai `GDRIVE_APPSCRIPT_URL`
6. Buat folder induk di Google Drive → salin ID-nya → isi ke `.env` sebagai `GDRIVE_FOLDER_ID`

> ⚠️ Setiap kali `google_apps_script.gs` diubah, wajib buat **New Deployment** baru dan perbarui URL di `.env`.

### Perilaku Upload

- Hanya file **per-outlet** yang diunggah (file master tidak dikirim ke Drive)
- Subfolder per outlet dibuat otomatis di Google Drive jika belum ada
- File lama di subfolder Drive akan di-**overwrite** jika ada nama yang sama
- Upload hanya mencakup outlet yang aktif pada sesi tersebut
- Jika `GDRIVE_APPSCRIPT_URL` kosong, proses upload dilewati tanpa error

### Upload Manual

```bash
# Upload semua file (master + subfolder outlet)
uv run python upload_to_gdrive.py

# Upload file tertentu saja
uv run python upload_to_gdrive.py --files path/ke/file.xlsx

# Override folder ID
uv run python upload_to_gdrive.py --folder-id YOUR_FOLDER_ID
```

---

## 📋 Sumber Data Master

Daftar outlet, cabang, Store ID, dan kredensial diambil dari **Google Sheets internal** (akses terbatas). Pipeline secara otomatis mem-filter hanya entri dengan:
- `Aplikasi` mengandung `Grab`
- `Status` = `Live`

> **Penting**: Kolom `Store ID` di Google Sheets harus diisi dengan `merchantID` dari Grab agar pencocokan data berjalan dengan benar untuk akun **Menu Groups** dan **Catalog Stores**.

---

## 🔐 File yang Diabaikan Git

| Path | Keterangan |
|---|---|
| `.env` | Konfigurasi Google Drive & kredensial |
| `laporan/` | Output laporan Excel |
| `logs/` | Log eksekusi |
| `*.xlsx`, `*.csv` | File laporan |
| `grab/sessions/` | Session Playwright (login tersimpan) |
| `grab/downloads/` | File JSON download sementara |
| `.venv/` | Virtual environment |

---

## 🐛 Troubleshooting

**File Excel kosong untuk cabang tertentu (AGSA, Roti Bakar 41, dll)**
> Pastikan kolom `Store ID` di Google Sheets diisi dengan `merchantID` yang benar dari Grab API. Scraper kini memprioritaskan pencocokan by Store ID.

**Upload gagal dengan HTTP 401**
> Periksa pengaturan deploy Google Apps Script: akses harus diset ke **"Anyone"** (bukan "Only myself" atau "Anyone with Google Account").

**Subfolder tidak terbuat di Google Drive**
> Pastikan Apps Script sudah di-deploy ulang setelah perubahan terbaru pada `google_apps_script.gs`. URL `/exec` yang lama tidak akan mengenali parameter `subFolderName`.

**Browser tidak muncul / crash**
> Set `"headless_grab": false` di `config.json` untuk mode visual, atau `true` untuk mode headless.

**Tidak ada merchant ditemukan (Cookie Mode)**
> Cookie mungkin sudah kedaluwarsa. Hapus file session di `grab/sessions/` dan jalankan ulang agar login ulang.

**Error `max_concurrency` menyebabkan blokir**
> Kurangi `max_concurrency` di `config.json` menjadi `1` atau `2` untuk koneksi lambat atau akun yang sering diblokir.

**Gagal fetch `catalog-stores` atau `menu-groups`**
> Lihat log di `grab/logs/`. Jika muncul `MerchantGroupID validation failed`, token/cookie yang digunakan tidak sesuai dengan grup yang diminta.

---

## 📄 Lisensi

Internal use only — [superfoodtech.id](https://superfoodtech.id)
