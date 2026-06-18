#!/usr/bin/env python3
import os
import sys
import base64
import requests
import mimetypes
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Kode warna ANSI untuk log terminal yang menarik (seperti di cli.py)
RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA = "\033[95m"

def upload_file_to_gdrive(file_path: str, script_url: str, folder_id: str = None, sub_folder_name: str = None) -> bool:
    """
    Mengirimkan file ke Google Apps Script Web App untuk disimpan di Google Drive.
    Jika sub_folder_name diberikan, file akan disimpan di subfolder tersebut di dalam folder induk.
    """
    path = Path(file_path)
    if not path.is_file():
        print(f"  {RED}❌ File tidak ditemukan: {file_path}{RESET}")
        return False

    file_name = path.name
    file_size_mb = path.stat().st_size / (1024 * 1024)
    
    location_label = f"{sub_folder_name}/{file_name}" if sub_folder_name else file_name
    print(f"  {CYAN}📄 Memproses file: {BOLD}{location_label}{RESET} ({file_size_mb:.2f} MB)...")
    
    # Deteksi mime type
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        # Fallback jika tidak terdeteksi (misal untuk format spreadsheet)
        if file_name.endswith('.xlsx'):
            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            mime_type = "application/octet-stream"

    # Batasi ukuran file (Apps Script memiliki batasan payload request sekitar 50MB,
    # namun disarankan di bawah 20MB agar tidak terkena timeout)
    if file_size_mb > 25:
        print(f"  {YELLOW}⚠️ Peringatan: File {file_name} cukup besar ({file_size_mb:.2f} MB). Upload mungkin lambat atau timeout.{RESET}")

    try:
        # Membaca data binary file
        with open(file_path, "rb") as f:
            file_data = f.read()

        # Encode ke Base64 agar aman ditransfer via JSON
        file_base64 = base64.b64encode(file_data).decode("utf-8")
        
        # Buat payload JSON
        payload = {
            "fileName": file_name,
            "fileBase64": file_base64,
            "mimeType": mime_type
        }
        if folder_id:
            payload["folderId"] = folder_id
        if sub_folder_name:
            payload["subFolderName"] = sub_folder_name

        headers = {
            "Content-Type": "application/json"
        }

        print(f"  {CYAN}📤 Mengirim file ke Google Apps Script...{RESET}")
        
        # Lakukan POST request. requests secara otomatis mengikuti redirect 302/303 
        # dari Google Script dengan merubahnya menjadi GET request ke Google Usercontent 
        # setelah request payload POST diproses.
        response = requests.post(script_url, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            try:
                res_json = response.json()
                if res_json.get("status") == "success":
                    print(f"  {GREEN}✓ Berhasil diunggah ke Google Drive!{RESET}")
                    if res_json.get("subFolder"):
                        created_label = " (folder baru dibuat)" if res_json.get("subFolderCreated") else " (folder sudah ada)"
                        print(f"    📂 Subfolder : {res_json.get('subFolder')}{created_label}")
                    print(f"    📂 ID Folder : {res_json.get('folderId')}")
                    print(f"    🆔 ID File   : {res_json.get('fileId')}")
                    print(f"    🔗 Link File : {CYAN}{res_json.get('url')}{RESET}")
                    return True
                else:
                    print(f"  {RED}❌ Server Apps Script menolak: {res_json.get('message')}{RESET}")
            except Exception:
                # Jika response bukan JSON yang valid
                print(f"  {RED}❌ Response dari server tidak valid: {response.text[:200]}{RESET}")
        else:
            print(f"  {RED}❌ HTTP Error {response.status_code}: {response.text[:200]}{RESET}")
            if response.status_code in (401, 403):
                print(f"\n  {YELLOW}💡 TIPS DIAGNOSIS ERROR {response.status_code}:{RESET}")
                print(f"  1. Pastikan Anda telah men-deploy Google Apps Script sebagai {BOLD}Web app{RESET}.")
                print(f"  2. Konfigurasikan opsi akses berikut saat deployment:")
                print(f"     - Execute as: {BOLD}Me (email-anda@gmail.com){RESET}")
                print(f"     - Who has access: {BOLD}Anyone{RESET} (⚠️ PENTING! Jangan pilih 'Only myself' atau 'Anyone with Google account').")
                print(f"  3. Pastikan URL di file .env berakhiran {BOLD}/exec{RESET} (contoh: .../macros/s/AKfycb.../exec).")
                print(f"     Jangan gunakan URL editor (berakhiran /edit) atau URL pengujian (berakhiran /dev).")
                print(f"  4. Jika Anda menggunakan akun Google Workspace (kantor/sekolah), administrator organisasi Anda")
                print(f"     mungkin melarang pembagian Web App ke luar organisasi (akses public/Anyone).\n")

    except requests.exceptions.Timeout:
        print(f"  {RED}❌ Timeout terjadi saat mengunggah {file_name}. Periksa koneksi internet Anda.{RESET}")
    except Exception as e:
        print(f"  {RED}❌ Terjadi kesalahan saat upload: {e}{RESET}")
        
    return False

def main():
    parser = argparse.ArgumentParser(description="Upload file laporan ke Google Drive via Google Apps Script")
    parser.add_argument("--files", nargs="+", help="Daftar file spesifik yang ingin diunggah (spasi dipisahkan)")
    parser.add_argument("--folder-id", type=str, help="Override ID Folder Google Drive")
    args = parser.parse_args()

    # Load file .env
    base_dir = Path(__file__).resolve().parent
    load_dotenv(base_dir / ".env", override=True)

    script_url = os.environ.get("GDRIVE_APPSCRIPT_URL")
    folder_id = args.folder_id or os.environ.get("GDRIVE_FOLDER_ID")

    print(f"\n{MAGENTA}{BOLD}================================================================{RESET}")
    print(f"  {BOLD}GOOGLE DRIVE UPLOADER VIA APPS SCRIPT{RESET}")
    print(f"{MAGENTA}================================================================{RESET}")

    if not script_url:
        print(f"{RED}[ERROR] GDRIVE_APPSCRIPT_URL tidak ditemukan di file .env!{RESET}")
        print(f"Silakan ikuti instruksi di {CYAN}google_apps_script.gs{RESET} untuk membuat Web App,")
        print(f"dan tambahkan baris berikut di file {CYAN}.env{RESET}:")
        print(f"  {BOLD}GDRIVE_APPSCRIPT_URL=https://script.google.com/macros/s/AKfycb.../exec{RESET}")
        sys.exit(1)

    # Menentukan file yang akan diunggah
    # Format: list of (file_path, sub_folder_name_or_None)
    files_to_upload = []  # list of (path_str, subfolder_str|None)
    if args.files:
        for f in args.files:
            files_to_upload.append((f, None))
    else:
        # Default: unggah file master (root) + file outlet (subfolder) dari laporan/menu
        laporan_menu_dir = base_dir / "laporan" / "menu"
        if laporan_menu_dir.is_dir():
            # File master di root laporan/menu
            for f in sorted(laporan_menu_dir.glob("*.xlsx")):
                files_to_upload.append((str(f), None))
            # File per-outlet di subfolder laporan/menu/<outlet>/
            for subfolder in sorted(laporan_menu_dir.iterdir()):
                if subfolder.is_dir():
                    for f in sorted(subfolder.glob("*.xlsx")):
                        files_to_upload.append((str(f), subfolder.name))

    if not files_to_upload:
        print(f"{YELLOW}[WARN] Tidak ada file yang ditemukan di '{base_dir / 'laporan' / 'menu'}'.{RESET}")
        print("Pastikan Anda sudah menjalankan scraper menu Grab terlebih dahulu.")
        sys.exit(0)

    print(f"Menggunakan URL Web App: {CYAN}{script_url[:50]}...{RESET}")
    if folder_id:
        print(f"Menggunakan ID Folder   : {YELLOW}{folder_id}{RESET}")
    else:
        print(f"Menggunakan ID Folder   : {YELLOW}[Default Apps Script / Root Drive]{RESET}")
    print(f"Jumlah file diantrekan  : {len(files_to_upload)}")
    print("-" * 64)

    success_count = 0
    for f_path, sub_folder in files_to_upload:
        success = upload_file_to_gdrive(f_path, script_url, folder_id, sub_folder_name=sub_folder)
        if success:
            success_count += 1
        print("-" * 64)

    print(f"\n{GREEN}{BOLD}✓ Selesai!{RESET} Berhasil mengunggah {success_count} dari {len(files_to_upload)} file ke Google Drive.")

if __name__ == "__main__":
    main()
