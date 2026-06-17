import argparse
import asyncio
import io
import os
import shutil
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv
import sys
import os

# Paksa encoding UTF-8 di Windows console agar karakter ✓ ❌ 🔍 tidak error
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


# --- Toggle Konfigurasi Global ---
ENABLE_GSHEETS_PUSH = False  # Set ke True untuk mengizinkan unggah ke Google Sheets

# Add current directory to sys.path to allow importing grab_api_scraper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

from grab_api_scraper import run_api_download_for_portal, validate_credentials

# --- Logging Setup ---
def setup_logger():
    os.makedirs("logs", exist_ok=True)
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = f"logs/grab_run_{timestamp}.log"
    
    # Only clean up non-log files (like old screenshots)
    for f in Path("logs").glob("*"):
        if f.is_file() and not f.name.endswith(".log"):
            try: f.unlink()
            except: pass

    logger = logging.getLogger("GrabAuto")
    logger.setLevel(logging.INFO)
    # Clear existing handlers if any (for notebook/interactive environments)
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

    # Console (dengan encoding utf-8 agar karakter unicode tidak crash di Windows)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    ch.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1, closefd=False)
    logger.addHandler(ch)

    # File
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger

log = setup_logger()

CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ3tLKBNXDqRgBw0mNhKZFxgvKx-JoiTDzm_s5Ix1cm7O6HCv4IvExOLR2HSRVaXSsx82V348mcr9X4/pub?gid=0&single=true&output=csv"

async def run_all(date_start: str = None, date_end: str = None, output_dir: str = None, user_filter: str = None, outlet_filter: str = None, branch_filter: str = None):
    # Reload env just in case
    load_dotenv(override=True)
    
    log.info(f"Fetching merchant list from spreadsheet...")
    try:
        resp = requests.get(CSV_URL, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text))
        
        # Filter for GrabFood and Status Live
        grab_df = df[df["Aplikasi"].str.contains("Grab", na=False, case=False)]
        grab_df = grab_df[grab_df["Status"].str.contains("Live", na=False, case=False)]
        
        portals = []
        for idx, row in grab_df.iterrows():
            user_sf = row.get("Nama Pengguna.1")
            user_mt = row.get("Nama Pengguna")
            pwd_sf = row.get("Kata Sandi.1")
            pwd_mt = row.get("Kata Sandi")
            
            user = user_sf if pd.notna(user_sf) and str(user_sf).strip() != "-" else user_mt
            pwd = pwd_sf if pd.notna(pwd_sf) and str(pwd_sf).strip() != "-" else pwd_mt
            
            if pd.notna(user) and pd.notna(pwd) and str(user).strip() != "-" and str(pwd).strip() != "-":
                u_str = str(user).strip()
                p_str = str(pwd).strip()
                outlet = str(row.get("Nama Outlet", "Unknown")).strip()
                
                # Di Master DB, kolom Cabang tidak ada, gunakan Brand
                branch_val = row.get("Cabang", row.get("Brand", ""))
                branch = str(branch_val).strip() if pd.notna(branch_val) else ""
                
                # Apply custom outlet and branch filters internally
                if outlet_filter:
                    if "|" in outlet_filter:
                        valid_outlets = [o.strip().lower() for o in outlet_filter.split("|")]
                        if str(outlet).strip().lower() not in valid_outlets: continue
                    elif str(outlet).strip().lower() != str(outlet_filter).strip().lower():
                        continue
                if branch_filter:
                    if "|" in branch_filter:
                        valid_branches = [b.strip().lower() for b in branch_filter.split("|")]
                        if str(branch).strip().lower() not in valid_branches: continue
                    elif str(branch).strip().lower() != str(branch_filter).strip().lower():
                        continue
                
                # Smart credential validation
                is_valid, err_msg = validate_credentials(u_str, p_str)
                if not is_valid:
                    log.warning(f"⚠️  [VALIDATION WARNING] Row #{idx+1} for '{outlet} ({branch})' has invalid credentials: {err_msg}")
                    
                portals.append({
                    "id": len(portals) + 1,
                    "outlet": outlet,
                    "branch": branch,
                    "user": u_str,
                    "pwd": p_str,
                    "shopee_short": str(row.get("Nama Pendek Outlet (Shopee) Final", "")).strip() if pd.notna(row.get("Nama Pendek Outlet (Shopee) Final")) else "",
                    "store_id": str(row.get("Store ID", "")).strip() if pd.notna(row.get("Store ID")) else ""
                })

        
    except Exception as e:
        log.error(f"Failed to fetch or parse spreadsheet: {e}")
        return

    # Determine output directory
    if output_dir:
        laporan_dir = Path(output_dir)
    else:
        laporan_dir = Path("laporan") / "menu"
    
    # Auto-cleanup old CSV files is disabled as per user request to keep existing files

    # ----------------------------------------------------------------
    # COOKIE MODE: gunakan direct HTTP request jika GRAB_COOKIE diset
    # ----------------------------------------------------------------
    grab_cookie = os.environ.get("GRAB_COOKIE", "").strip()
    if grab_cookie:
        log.info("="*60)
        log.info("  [COOKIE MODE] Direct HTTP Request — tanpa browser")
        log.info(f"  Total portals dari spreadsheet : {len(portals)}")
        log.info("="*60)

        from grab_api_scraper import run_cookie_download

        downloaded_file, err = run_cookie_download(grab_cookie)
        if not downloaded_file:
            log.error(f"[Cookie Mode] Download gagal: {err}")
            return

        import json as _json
        with open(downloaded_file, "r", encoding="utf-8") as f:
            scraped = _json.load(f)
        items_all = scraped.get("items", [])
        mods_all  = scraped.get("modifiers", [])

        def _clean(name):
            return "".join(c for c in str(name).lower() if c.isalnum())

        laporan_dir.mkdir(parents=True, exist_ok=True)

        item_cols = [
            "Link outlet", "Nama panjang", "Store ID",
            "Nama kategori", "Nama item", "Jumlah terjual", "Jumlah modifier group",
            "Jumlah modifier", "Deskripsi item", "Harga item sebelum promo (harga coret)",
            "Harga item setelah promo (harga coret)", "Nominal atau persentase promo (harga coret)",
            "Ketersediaan item", "Link foto"
        ]
        mod_cols = [
            "Link outlet", "Nama panjang", "Store ID",
            "Nama item", "Nama modifier group", "Nama modifier", "Tipe modifier",
            "Minimal", "Maksimal", "Harga modifier", "Ketersediaan modifier"
        ]

        for portal in portals:
            portal_id   = portal["id"]
            outlet_name = f"{portal['outlet']} ({portal['branch']})" if portal['branch'] else portal['outlet']
            safe_name   = (f"{portal['outlet']}_{portal['branch']}" if portal['branch'] else portal['outlet']).replace("/", "_").replace("\\", "_")
            t_clean     = _clean(portal['outlet'])

            def _patch(row, portal=portal):
                r = dict(row)
                r["Nama panjang"] = portal["outlet"]
                if portal["store_id"]:
                    r["Store ID"] = portal["store_id"]
                return r

            matched_items = [_patch(x) for x in items_all if t_clean in _clean(x.get("Nama panjang", "")) or _clean(x.get("Nama panjang", "")) in t_clean]
            matched_mods  = [_patch(x) for x in mods_all  if t_clean in _clean(x.get("Nama panjang", "")) or _clean(x.get("Nama panjang", "")) in t_clean]

            # Fallback jika 1 portal dan tidak ada match nama
            if not matched_items and len(portals) == 1:
                matched_items = [_patch(x) for x in items_all]
                matched_mods  = [_patch(x) for x in mods_all]

            df_items = pd.DataFrame(matched_items)
            df_mods  = pd.DataFrame(matched_mods)

            if df_items.empty:
                df_items = pd.DataFrame(columns=item_cols)
            else:
                for col in item_cols:
                    if col not in df_items.columns: df_items[col] = ""
                df_items = df_items[item_cols]

            if df_mods.empty:
                df_mods = pd.DataFrame(columns=mod_cols)
            else:
                for col in mod_cols:
                    if col not in df_mods.columns: df_mods[col] = ""
                df_mods = df_mods[mod_cols]

            # Overwrite approach for two separate files (Cookie Mode)
            item_xlsx = laporan_dir / f"{safe_name}_menu_item.xlsx"
            mod_xlsx  = laporan_dir / f"{safe_name}_menu_modifier.xlsx"
            
            # Hapus file lama jika ada
            for f in (item_xlsx, mod_xlsx):
                try: f.unlink()
                except Exception: pass

            with pd.ExcelWriter(item_xlsx, engine="openpyxl") as writer:
                df_items.to_excel(writer, sheet_name="Item", index=False)
            with pd.ExcelWriter(mod_xlsx, engine="openpyxl") as writer:
                df_mods.to_excel(writer, sheet_name="Modifier", index=False)

            log.info(f"  ✓ [PORTAL {portal_id}] {outlet_name} — {len(matched_items)} items, {len(matched_mods)} modifiers → {item_xlsx.name} & {mod_xlsx.name}")

        # --- Master merge (cookie mode) ---
        log.info("="*60)
        log.info("  [COOKIE MODE] SEMUA PORTAL SELESAI")
        log.info("="*60)

        # Merge Items
        item_files = sorted(laporan_dir.glob("*_menu_item.xlsx")) if laporan_dir.exists() else []
        item_files = [f for f in item_files if f.name != "0Master_menu_item.xlsx" and not f.name.startswith("MASTER_") and not f.name.startswith("CUSTOM_")]
        if outlet_filter or branch_filter:
            valid_stems = set()
            for p_info in portals:
                ps = (f"{p_info['outlet']}_{p_info['branch']}" if p_info['branch'] else p_info['outlet']).replace("/", "_").replace("\\", "_")
                valid_stems.add(f"{ps}_menu_item")
            item_files = [f for f in item_files if f.stem in valid_stems]

        all_items = []
        if item_files:
            for xp in item_files:
                try:
                    df = pd.read_excel(xp, sheet_name="Item", dtype=str)
                    if not df.empty: all_items.append(df)
                    log.info(f"  🔍 [MERGE ITEM] Loaded '{xp.name}' | Items: {len(df)}")
                except Exception as e:
                    log.error(f"  ❌ Gagal baca '{xp.name}': {e}")
        
        master_items = pd.concat(all_items, ignore_index=True) if all_items else pd.DataFrame(columns=item_cols)
        master_item_xlsx = laporan_dir / "0Master_menu_item.xlsx"
        try: master_item_xlsx.unlink()
        except Exception: pass
        with pd.ExcelWriter(master_item_xlsx, engine="openpyxl") as writer:
            master_items.to_excel(writer, sheet_name="Item", index=False)

        # Merge Modifiers
        mod_files = sorted(laporan_dir.glob("*_menu_modifier.xlsx")) if laporan_dir.exists() else []
        mod_files = [f for f in mod_files if f.name != "0Master_menu_modifier.xlsx" and not f.name.startswith("MASTER_") and not f.name.startswith("CUSTOM_")]
        if outlet_filter or branch_filter:
            valid_stems = set()
            for p_info in portals:
                ps = (f"{p_info['outlet']}_{p_info['branch']}" if p_info['branch'] else p_info['outlet']).replace("/", "_").replace("\\", "_")
                valid_stems.add(f"{ps}_menu_modifier")
            mod_files = [f for f in mod_files if f.stem in valid_stems]

        all_mods = []
        if mod_files:
            for xp in mod_files:
                try:
                    df = pd.read_excel(xp, sheet_name="Modifier", dtype=str)
                    if not df.empty: all_mods.append(df)
                    log.info(f"  🔍 [MERGE MODIFIER] Loaded '{xp.name}' | Modifiers: {len(df)}")
                except Exception as e:
                    log.error(f"  ❌ Gagal baca '{xp.name}': {e}")
                    
        master_mods = pd.concat(all_mods, ignore_index=True) if all_mods else pd.DataFrame(columns=mod_cols)
        master_mod_xlsx = laporan_dir / "0Master_menu_modifier.xlsx"
        try: master_mod_xlsx.unlink()
        except Exception: pass
        with pd.ExcelWriter(master_mod_xlsx, engine="openpyxl") as writer:
            master_mods.to_excel(writer, sheet_name="Modifier", index=False)

        log.info(f"✓ Laporan Master: {master_item_xlsx} & {master_mod_xlsx}")
        log.info(f"  Total Baris Item     : {len(master_items):,}")
        log.info(f"  Total Baris Modifier : {len(master_mods):,}")

        return  # selesai, skip Playwright mode

    log.info("="*60)
    log.info(f"  GRAB MULTI-PORTAL AUTOMATION ({len(portals)} portals)")
    
    unique_users = {}
    for p_info in portals:
        u = p_info["user"]
        if user_filter and user_filter.lower() not in u.lower():
            continue

        if u not in unique_users:
            unique_users[u] = {"pwd": p_info["pwd"], "portals": []}
        unique_users[u]["portals"].append(p_info)
    
    log.info(f"  Unique Accounts: {len(unique_users)}")
    log.info("="*60)
    
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        # Load headless setting and concurrency from config.json walk-up
        headless_env = True
        concurrency_limit = 3
        try:
            import json
            for parent in Path(__file__).resolve().parents:
                config_file = parent / "config.json"
                if config_file.exists():
                    with open(config_file, "r") as f:
                        config_data = json.load(f)
                        headless_env = config_data.get("headless_grab", True)
                        concurrency_limit = config_data.get("max_concurrency", 3)
                    break
        except Exception:
            pass
        browser = await p.chromium.launch(headless=headless_env)
        semaphore = asyncio.Semaphore(concurrency_limit)
        failures = []

        async def process_user(username, info):
            password = info["pwd"]
            related_portals = info["portals"]
            first_outlet = related_portals[0]["outlet"]
            
            async with semaphore:
                log.info(f"[ACCOUNT] Starting for: {username} ({first_outlet})")
                try:
                    downloaded_file, err = await run_api_download_for_portal(
                        username, password, 
                        start_date=date_start, 
                        end_date=date_end,
                        browser=browser
                    )

                    if not downloaded_file:
                        log.error(f"  ✗ [ACCOUNT] {username} Failed: {err}")
                        failures.append({"user": username, "error": err, "outlets": [p["outlet"] for p in related_portals]})
                        return

                    def clean_name(name):
                        return "".join(c for c in str(name).lower() if c.isalnum())

                    # Load items/modifiers from JSON
                    import json
                    with open(downloaded_file, "r", encoding="utf-8") as f:
                        scraped = json.load(f)
                    items = scraped.get("items", [])
                    modifiers = scraped.get("modifiers", [])

                    for portal in related_portals:
                        portal_id = portal["id"]
                        outlet_name = f"{portal['outlet']} ({portal['branch']})" if portal['branch'] else portal['outlet']
                        laporan_dir.mkdir(parents=True, exist_ok=True)
                        
                        portal_safe_name = f"{portal['outlet']}_{portal['branch']}" if portal['branch'] else f"{portal['outlet']}"
                        portal_safe_name = portal_safe_name.replace("/", "_").replace("\\", "_")
                        
                        matched_items = []
                        matched_modifiers = []
                        
                        target_clean = clean_name(portal['outlet'])
                        
                        for item in items:
                            item_clean = clean_name(item["Nama panjang"])
                            if target_clean in item_clean or item_clean in target_clean:
                                item_copy = dict(item)
                                item_copy["Nama panjang"] = portal["outlet"]
                                if portal["store_id"]:
                                    item_copy["Store ID"] = portal["store_id"]
                                matched_items.append(item_copy)
                                
                        for mod in modifiers:
                            mod_clean = clean_name(mod["Nama panjang"])
                            if target_clean in mod_clean or mod_clean in target_clean:
                                mod_copy = dict(mod)
                                mod_copy["Nama panjang"] = portal["outlet"]
                                if portal["store_id"]:
                                    mod_copy["Store ID"] = portal["store_id"]
                                matched_modifiers.append(mod_copy)
                                
                        if not matched_items and len(related_portals) == 1:
                            for item in items:
                                item_copy = dict(item)
                                item_copy["Nama panjang"] = portal["outlet"]
                                if portal["store_id"]:
                                    item_copy["Store ID"] = portal["store_id"]
                                matched_items.append(item_copy)
                            for mod in modifiers:
                                mod_copy = dict(mod)
                                mod_copy["Nama panjang"] = portal["outlet"]
                                if portal["store_id"]:
                                    mod_copy["Store ID"] = portal["store_id"]
                                matched_modifiers.append(mod_copy)

                        item_xlsx = laporan_dir / f"{portal_safe_name}_menu_item.xlsx"
                        mod_xlsx  = laporan_dir / f"{portal_safe_name}_menu_modifier.xlsx"
                        
                        # Hapus file lama jika ada
                        for f in (item_xlsx, mod_xlsx):
                            try: f.unlink()
                            except Exception: pass

                        df_items = pd.DataFrame(matched_items)
                        df_mods = pd.DataFrame(matched_modifiers)
                        
                        item_cols = [
                            "Link outlet", "Nama panjang", "Store ID",
                            "Nama kategori", "Nama item", "Jumlah terjual", "Jumlah modifier group",
                            "Jumlah modifier", "Deskripsi item", "Harga item sebelum promo (harga coret)",
                            "Harga item setelah promo (harga coret)", "Nominal atau persentase promo (harga coret)",
                            "Ketersediaan item", "Link foto"
                        ]
                        mod_cols = [
                            "Link outlet", "Nama panjang", "Store ID",
                            "Nama item", "Nama modifier group", "Nama modifier", "Tipe modifier",
                            "Minimal", "Maksimal", "Harga modifier", "Ketersediaan modifier"
                        ]
                        
                        if df_items.empty:
                            df_items = pd.DataFrame(columns=item_cols)
                        else:
                            for col in item_cols:
                                if col not in df_items.columns:
                                    df_items[col] = ""
                            df_items = df_items[item_cols]
                            
                        if df_mods.empty:
                            df_mods = pd.DataFrame(columns=mod_cols)
                        else:
                            for col in mod_cols:
                                if col not in df_mods.columns:
                                    df_mods[col] = ""
                            df_mods = df_mods[mod_cols]

                        with pd.ExcelWriter(item_xlsx, engine="openpyxl") as writer:
                            df_items.to_excel(writer, sheet_name="Item", index=False)
                        with pd.ExcelWriter(mod_xlsx, engine="openpyxl") as writer:
                            df_mods.to_excel(writer, sheet_name="Modifier", index=False)
                            
                        log.info(f"  ✓ [PORTAL {portal_id}] {outlet_name} — Saved to: {item_xlsx.name} & {mod_xlsx.name}")

                except Exception as e:
                    log.error(f"  ✗ [ACCOUNT] {username} CRITICAL ERROR: {str(e)}")

        tasks = [process_user(u, info) for u, info in unique_users.items()]
        await asyncio.gather(*tasks)
        
        # --- Sequential Retry for Failed Accounts ---
        if failures:
            log.info("\n" + "="*60)
            log.info(f"  [RETRY] Attempting to re-run {len(failures)} failed accounts sequentially to resolve network/concurrency issues...")
            log.info("="*60)
            
            retry_failures = list(failures)
            failures.clear() # Clear so it only contains true failures after retry
            
            for f in retry_failures:
                username = f["user"]
                info = unique_users[username]
                log.info(f"\n  [RETRY ACCOUNT] Re-running sequentially for: {username}")
                await process_user(username, info)
                
        await browser.close()

    log.info("="*60)
    log.info("  ALL PORTALS FINISHED PROCESSING")
    if failures:
        log.info("-" * 60)
        log.info(f"  FAILED ACCOUNTS ({len(failures)}):")
        for f in failures:
            log.info(f"  - {f['user']}: {f['error']}")
    else:
        log.info("  ✓ ALL ACCOUNTS PROCESSED SUCCESSFULLY")
    log.info("="*60)

    # --- Gabungkan semua XLSX menjadi file master ---
    if output_dir:
        laporan_dir = Path(output_dir)
    else:
        laporan_dir = Path("laporan") / "menu"

    # Merge Items
    item_files = sorted(laporan_dir.glob("*_menu_item.xlsx")) if laporan_dir.exists() else []
    item_files = [f for f in item_files if f.name != "0Master_menu_item.xlsx" and not f.name.startswith("MASTER_") and not f.name.startswith("CUSTOM_")]
    if outlet_filter or branch_filter:
        valid_stems = set()
        for p_info in portals:
            ps = (f"{p_info['outlet']}_{p_info['branch']}" if p_info['branch'] else p_info['outlet']).replace("/", "_").replace("\\", "_")
            valid_stems.add(f"{ps}_menu_item")
        item_files = [f for f in item_files if f.stem in valid_stems]

    print(f"\nScanning and merging {len(item_files)} raw item menu Excel files...")
    all_items_frames = []
    
    for xlsx_path in item_files:
        try:
            df_item = pd.read_excel(xlsx_path, sheet_name="Item", dtype=str)
            if not df_item.empty:
                all_items_frames.append(df_item)
            print(f"  🔍 [MERGE ITEM] Loaded '{xlsx_path.name}' | Items: {len(df_item)}")
        except Exception as e:
            print(f"  ❌ [MERGE ITEM] Gagal membaca '{xlsx_path.name}': {e}")

    # Merge Modifiers
    mod_files = sorted(laporan_dir.glob("*_menu_modifier.xlsx")) if laporan_dir.exists() else []
    mod_files = [f for f in mod_files if f.name != "0Master_menu_modifier.xlsx" and not f.name.startswith("MASTER_") and not f.name.startswith("CUSTOM_")]
    if outlet_filter or branch_filter:
        valid_stems = set()
        for p_info in portals:
            ps = (f"{p_info['outlet']}_{p_info['branch']}" if p_info['branch'] else p_info['outlet']).replace("/", "_").replace("\\", "_")
            valid_stems.add(f"{ps}_menu_modifier")
        mod_files = [f for f in mod_files if f.stem in valid_stems]

    print(f"\nScanning and merging {len(mod_files)} raw modifier menu Excel files...")
    all_mods_frames = []
    
    for xlsx_path in mod_files:
        try:
            df_mod = pd.read_excel(xlsx_path, sheet_name="Modifier", dtype=str)
            if not df_mod.empty:
                all_mods_frames.append(df_mod)
            print(f"  🔍 [MERGE MODIFIER] Loaded '{xlsx_path.name}' | Modifiers: {len(df_mod)}")
        except Exception as e:
            print(f"  ❌ [MERGE MODIFIER] Gagal membaca '{xlsx_path.name}': {e}")

    # Combine
    item_cols = [
        "Link outlet", "Nama panjang", "Store ID",
        "Nama kategori", "Nama item", "Jumlah terjual", "Jumlah modifier group",
        "Jumlah modifier", "Deskripsi item", "Harga item sebelum promo (harga coret)",
        "Harga item setelah promo (harga coret)", "Nominal atau persentase promo (harga coret)",
        "Ketersediaan item", "Link foto"
    ]
    mod_cols = [
        "Link outlet", "Nama panjang", "Store ID",
        "Nama item", "Nama modifier group", "Nama modifier", "Tipe modifier",
        "Minimal", "Maksimal", "Harga modifier", "Ketersediaan modifier"
    ]

    master_items = pd.concat(all_items_frames, ignore_index=True) if all_items_frames else pd.DataFrame(columns=item_cols)
    master_mods = pd.concat(all_mods_frames, ignore_index=True) if all_mods_frames else pd.DataFrame(columns=mod_cols)

    master_item_xlsx = laporan_dir / "0Master_menu_item.xlsx"
    master_mod_xlsx = laporan_dir / "0Master_menu_modifier.xlsx"
    
    for old_f in (master_item_xlsx, master_mod_xlsx):
        try: old_f.unlink()
        except Exception: pass

    with pd.ExcelWriter(master_item_xlsx, engine="openpyxl") as writer:
        master_items.to_excel(writer, sheet_name="Item", index=False)
    with pd.ExcelWriter(master_mod_xlsx, engine="openpyxl") as writer:
        master_mods.to_excel(writer, sheet_name="Modifier", index=False)

    log.info(f"✓ Laporan Master Excel Gabungan: {master_item_xlsx} & {master_mod_xlsx}")
    log.info(f"  Total Baris Item     : {len(master_items):,}")
    log.info(f"  Total Baris Modifier : {len(master_mods):,}")

    if ENABLE_GSHEETS_PUSH:
        log.info("\n📤 [PROGRESS] Distribusi ke Google Sheets (Menu) tidak didukung dalam integrasi baru ini. Melewati.")
    else:
        log.info("\n⏭️ [SKIP] Distribusi ke Google Sheets dinonaktifkan secara global.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Jalankan scraper Grab multi-portal dan hitung omzet."
    )
    parser.add_argument(
        "--start-date",
        default=None,
        help="Filter awal (inklusif), format YYYY-MM-DD. Contoh: 2026-02-01",
    )
    parser.add_argument(
        "--end-date",
        default=None,
        help="Filter akhir (inklusif), format YYYY-MM-DD. Contoh: 2026-04-30",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Override output directory for reports.",
    )
    parser.add_argument(
        "--user",
        default=None,
        help="Filter specific username to run.",
    )
    parser.add_argument(
        "--outlet",
        default=None,
        help="Filter specific outlet name to run.",
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Filter specific branch name to run.",
    )
    args = parser.parse_args()
    asyncio.run(run_all(
        date_start=args.start_date, 
        date_end=args.end_date, 
        output_dir=args.output_dir, 
        user_filter=args.user,
        outlet_filter=args.outlet,
        branch_filter=args.branch
    ))
