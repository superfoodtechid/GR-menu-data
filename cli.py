#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  GET OUTLET DATA GRAB — Unified Weekly Transaction Pipeline
═══════════════════════════════════════════════════════════════
"""

import argparse
import asyncio
import sys
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add parent directory to sys.path so core/ imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure UTF-8 output encoding for windows consoles to prevent UnicodeEncodeErrors
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# Date normalization function has been removed since this is a static menu scraper.

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
RED    = "\033[91m"
MAGENTA = "\033[95m"
DIM    = "\033[2m"

def banner():
    title = "GET OUTLET DATA GRAB"
    border = "=" * 65
    print(f"\033[38;5;238m{border}\033[0m")
    print(f"  \033[1;38;5;208m★ \033[1;38;5;220m{title.center(59)} \033[1;38;5;208m★\033[0m")
    print(f"\033[38;5;238m{border}\033[0m")
    print()

def _resolve_python_executable() -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(base, ".venv", "bin", "python")
    if os.path.isfile(venv_python):
        return venv_python
    parent_venv = os.path.join(os.path.dirname(base), "src", ".venv", "bin", "python")
    if os.path.isfile(parent_venv):
        return parent_venv
    return sys.executable

def _resolve_output_dir(platform_name: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(base, "laporan", "menu")
    os.makedirs(out, exist_ok=True)
    return out

def clear_local_data():
    output_dir = _resolve_output_dir("grab")
    if os.path.exists(output_dir):
        import shutil
        print(f"\n  {YELLOW}[INFO] Menghapus data laporan lokal di: {output_dir}...{RESET}")
        deleted_files = 0
        deleted_dirs = 0
        for item in os.listdir(output_dir):
            item_path = os.path.join(output_dir, item)
            try:
                if os.path.isfile(item_path):
                    os.unlink(item_path)
                    deleted_files += 1
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted_dirs += 1
            except Exception as e:
                print(f"  {RED}[ERROR] Gagal menghapus {item}: {e}{RESET}")
        print(f"  {GREEN}✓ Selesai! Berhasil menghapus {deleted_files} file dan {deleted_dirs} folder laporan lokal.{RESET}")
    else:
        print(f"\n  {CYAN}[INFO] Direktori laporan kosong/tidak ditemukan.{RESET}")
    import time
    time.sleep(2)

def run_grab(user_filter: str = None, outlet_filter: str = None, branch_filter: str = None):
    grab_dir = os.path.join(os.path.dirname(__file__), "grab")
    if not os.path.isdir(grab_dir):
        print(f"{RED}[ERROR]{RESET} Grab directory not found: {grab_dir}")
        return False

    output_dir = _resolve_output_dir("grab")
    import subprocess
    python_exe = _resolve_python_executable()
    cmd = [
        python_exe, "main.py",
        "--output-dir", output_dir,
    ]
    if user_filter: cmd.extend(["--user", user_filter])
    if outlet_filter: cmd.extend(["--outlet", outlet_filter])
    if branch_filter: cmd.extend(["--branch", branch_filter])

    print(f"\n{GREEN}{BOLD}▶ GRAB MENU SCRAPER PIPELINE{RESET}")
    result = subprocess.run(cmd, cwd=grab_dir)
    return result.returncode == 0


def interactive_mode():
    state = "scope"
    
    platform = "grab"
    scope_choice = None
    outlet = []
    branch = []
    
    df_main = None
    def load_df():
        nonlocal df_main
        if df_main is not None:
            return df_main
        import pandas as pd
        import requests
        import io
        print(f"\n  {CYAN}[INFO] Mengunduh daftar merchant terbaru dari Google Sheets...{RESET}")
        CSV_URL_MAIN = "https://docs.google.com/spreadsheets/d/14eCb8DAEXhmbYj9MFj2KzC7AhkulbCbSNPltN2m-go0/export?format=csv&gid=0"
        try:
            import time
            cache_buster = f"&t={int(time.time())}" if "?" in CSV_URL_MAIN else f"?t={int(time.time())}"
            resp_main = requests.get(CSV_URL_MAIN + cache_buster, timeout=30)
            resp_main.raise_for_status()
            df_main = pd.read_csv(io.StringIO(resp_main.text))
            return df_main
        except Exception as e:
            print(f"  {RED}[ERROR] Gagal mengunduh Google Sheets: {e}{RESET}")
            sys.exit(1)

    while True:
        if state == "scope":
            os.system('cls' if os.name == 'nt' else 'clear')
            banner()
            print(f"  {BOLD}Pilih cakupan outlet:{RESET}")
            print(f"    {GREEN}[1]{RESET} Pilih semua outlet")
            print(f"    {YELLOW}[2]{RESET} Pilih custom (Filter spesifik){RESET}")
            print(f"    {CYAN}[3]{RESET} Bersihkan data laporan lokal (Clear local data){RESET}")
            print(f"    {RED}[4]{RESET} Keluar")
            print()
            
            scope_choice = input(f"  {BOLD}Pilihan (1/2/3/4):{RESET} ").strip()
            if scope_choice == "4":
                print("  Keluar.")
                sys.exit(0)
            elif scope_choice == "1":
                outlet = []
                branch = []
                state = "confirm"
            elif scope_choice == "2":
                df_main = load_df()
                state = "grab_outlet"
            elif scope_choice == "3":
                clear_local_data()
            else:
                print(f"  {RED}Input tidak valid. Masukkan 1, 2, 3, atau 4.{RESET}")
                import time
                time.sleep(1)

        elif state == "grab_outlet":
            df_grab = df_main[df_main["Aplikasi"].str.contains("Grab", na=False, case=False) & df_main["Status"].str.contains("Live", na=False, case=False)]
            if df_grab.empty:
                print(f"  {RED}[ERROR] Tidak ada outlet Grab di Google Sheets.{RESET}")
                state = "scope"
                continue
                
            outlets_list = sorted(df_grab["Nama Outlet"].dropna().unique())
            print(f"\n  {BOLD}Pilih Outlet Grab:{RESET}")
            for idx, o_name in enumerate(outlets_list):
                print(f"    {GREEN}[{idx + 1}]{RESET} {o_name}")
            print(f"    {CYAN}[b]{RESET} Kembali ke cakupan outlet")
            print()
            
            o_choices = input(f"  {BOLD}Pilih nomor outlet Grab (contoh: 1,3 atau 'all' atau 'b'):{RESET} ").strip()
            if o_choices.lower() == "b":
                state = "scope"
            elif o_choices.lower() == "all":
                outlet = outlets_list
                state = "confirm"
            else:
                try:
                    indices = [int(x.strip()) for x in o_choices.split(",") if x.strip()]
                    if all(1 <= i <= len(outlets_list) for i in indices):
                        outlet = [outlets_list[i - 1] for i in indices]
                        if len(outlet) == 1:
                            state = "grab_branch"
                        else:
                            branch = []
                            state = "confirm"
                    else:
                        print(f"  {RED}Pilihan tidak valid.{RESET}")
                except ValueError:
                    print(f"  {RED}Pilihan tidak valid.{RESET}")

        elif state == "grab_branch":
            df_grab = df_main[df_main["Aplikasi"].str.contains("Grab", na=False, case=False) & df_main["Status"].str.contains("Live", na=False, case=False)]
            df_branch = df_grab[df_grab["Nama Outlet"] == outlet[0]]
            branch_col = "Cabang" if "Cabang" in df_branch.columns else "Brand"
            branches = sorted(df_branch[branch_col].dropna().unique()) if branch_col in df_branch.columns else []
            
            print(f"\n  {BOLD}Pilih Cabang Grab untuk '{outlet[0]}':{RESET}")
            for idx, b_name in enumerate(branches):
                print(f"    {GREEN}[{idx + 1}]{RESET} {b_name}")
            print(f"    {CYAN}[b]{RESET} Kembali ke pemilihan outlet Grab")
            print()
            
            b_choices = input(f"  {BOLD}Pilih nomor cabang Grab (contoh: 1,2 atau 'all' atau 'b'):{RESET} ").strip()
            if b_choices.lower() == "b":
                state = "grab_outlet"
            elif b_choices.lower() == "all":
                branch = branches
                state = "confirm"
            else:
                try:
                    indices = [int(x.strip()) for x in b_choices.split(",") if x.strip()]
                    if all(1 <= i <= len(branches) for i in indices):
                        branch = [branches[i - 1] for i in indices]
                        state = "confirm"
                    else:
                        print(f"  {RED}Pilihan tidak valid.{RESET}")
                except ValueError:
                    print(f"  {RED}Pilihan tidak valid.{RESET}")

        elif state == "confirm":
            load_dotenv()
            grab_cookie = os.environ.get("GRAB_COOKIE", "").strip()
            mode_label  = f"{GREEN}Cookie (Direct Request){RESET}" if grab_cookie else f"{YELLOW}Browser Login (Playwright){RESET}"
            print(f"\n  {CYAN}{'─'*50}{RESET}")
            print(f"  Platform : {BOLD}Grab{RESET}")
            print(f"  Mode     : {BOLD}{mode_label}{RESET}")
            if scope_choice == "2":
                if outlet: print(f"  Grab Outlet : {BOLD}{outlet} ({branch}){RESET}")
            else:
                print(f"  Outlet   : {BOLD}Semua Outlet{RESET}")
            print(f"  {CYAN}{'─'*50}{RESET}")
            
            print(f"  {BOLD}Konfirmasi tindakan:{RESET}")
            print(f"    {GREEN}[1]{RESET} Lanjutkan")
            print(f"    {YELLOW}[2]{RESET} Kembali ke pemilihan cakupan")
            print(f"    {RED}[3]{RESET} Batal dan Keluar")
            print()
            
            confirm = input(f"  {BOLD}Pilihan (1/2/3):{RESET} ").strip()
            if confirm == "1":
                break
            elif confirm == "2":
                state = "scope"
            elif confirm == "3":
                print("  Dibatalkan.")
                sys.exit(0)
            else:
                print(f"  {RED}Pilihan tidak valid.{RESET}")

    return platform, outlet, branch

def main():
    parser = argparse.ArgumentParser(description="GET OUTLET DATA GRAB — Unified Menu Scraper Pipeline")
    parser.add_argument("platform", nargs="?", default="grab", help="Platform: grab (default)")
    parser.add_argument("--user", type=str, default=None, help="Filter specific username (Grab only)")
    parser.add_argument("--outlet", type=str, default=None, help="Filter specific outlet name")
    parser.add_argument("--branch", type=str, default=None, help="Filter specific branch name")
    args = parser.parse_args()

    load_dotenv()

    platform = args.platform.lower()
    if platform == "shopee":
        print(f"{RED}[ERROR] Shopee automation has been removed.{RESET}")
        sys.exit(1)

    if args.outlet is None and args.branch is None:
        _, outlet, branch = interactive_mode()
    else:
        outlet = [args.outlet] if args.outlet else []
        branch = [args.branch] if args.branch else []
        banner()

    results = {}
    start_time = datetime.now()

    o_str = "|".join(outlet) if outlet else None
    b_str = "|".join(branch) if branch else None
    results["Grab"] = run_grab(user_filter=args.user, outlet_filter=o_str, branch_filter=b_str)

    elapsed = datetime.now() - start_time
    print(f"\n{CYAN}{BOLD}  SUMMARY{RESET}")
    print(f"  Duration: {int(elapsed.total_seconds() // 60)}m {int(elapsed.total_seconds() % 60)}s")
    for name, success in results.items():
        status = f"{GREEN}✓ SUCCESS{RESET}" if success else f"{RED}✗ FAILED{RESET}"
        print(f"  {name:10s} : {status}")

if __name__ == "__main__":
    main()
