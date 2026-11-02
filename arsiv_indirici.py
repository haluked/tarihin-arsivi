"""
Tarihin Arka Odası — Otomatik Video İndirici (Arşivden Yerel Diske)
İnternet Archive / Archivarix üzerinden doğrudan .webm streamlerini indirir.

Kullanım:
  python arsiv_indirici.py --test            (İlk 1 videoyu test amaçlı indirir)
  python arsiv_indirici.py --limit 5         (5 video indirir)
  python arsiv_indirici.py --ep 199          (Belirli bir bölümü indirir)
  python arsiv_indirici.py --all             (Arşivde bulunan 144 videonun tamamını sırayla indirir)
  python arsiv_indirici.py --generate-scripts (IDM / JDownloader / curl için indirme listesi üretir)
"""

import sys
import os
import json
import time
import argparse
import urllib.request
import re

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = "arsivden indirilenler"
RESULTS_FILE = "tam_arsiv_tarama_sonuclari.json"

def clean_filename(name):
    # Windows forbidden characters: \ / : * ? " < > |
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r'\s+', " ", cleaned).strip()
    return cleaned

def load_archive_results():
    if not os.path.exists(RESULTS_FILE):
        print(f"HATA: {RESULTS_FILE} bulunamadı.")
        return []
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def download_video(item, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    
    p_no = item['id']
    date_tr = item['date_tr']
    topic = item.get('topic') or 'Konu Belirtilmedi'
    vid = item['old_video_id']
    
    # Direct endpoint that redirects to Wayback WebM
    download_url = f"https://tube.archivarix.net/api/videos/{vid}/file"
    
    safe_topic = clean_filename(topic)[:40]
    filename = f"[No {p_no}] {date_tr} - {safe_topic}.webm"
    dest_path = os.path.join(output_dir, filename)
    part_path = dest_path + ".part"

    # Check if already fully downloaded
    if os.path.exists(dest_path):
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"✓ Zaten indirilmiş ({size_mb:.1f} MB): {filename}")
        return True

    downloaded_bytes = 0
    if os.path.exists(part_path):
        downloaded_bytes = os.path.getsize(part_path)

    print(f"\nİndiriliyor: [{p_no}] {date_tr} - {safe_topic}")
    print(f"Hedef: {filename}")
    if downloaded_bytes > 0:
        print(f"Kaldığı yerden devam ediliyor: {downloaded_bytes / (1024*1024):.1f} MB")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) TarihinArsivi/1.0'
    }
    if downloaded_bytes > 0:
        headers['Range'] = f"bytes={downloaded_bytes}-"

    req = urllib.request.Request(download_url, headers=headers)
    
    try:
        start_time = time.time()
        last_print = start_time
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            total_size = resp.headers.get('Content-Length')
            if total_size is not None:
                total_size = int(total_size) + downloaded_bytes
            
            mode = 'ab' if downloaded_bytes > 0 else 'wb'
            with open(part_path, mode) as f:
                current_downloaded = downloaded_bytes
                chunk_size = 1024 * 256  # 256 KB chunks
                
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    current_downloaded += len(chunk)
                    
                    now = time.time()
                    if now - last_print >= 1.0:
                        last_print = now
                        elapsed = now - start_time
                        speed_mb = (current_downloaded - downloaded_bytes) / (1024 * 1024 * max(elapsed, 0.001))
                        
                        if total_size:
                            pct = (current_downloaded / total_size) * 100
                            mb_curr = current_downloaded / (1024 * 1024)
                            mb_total = total_size / (1024 * 1024)
                            rem_bytes = total_size - current_downloaded
                            eta_s = rem_bytes / max(speed_mb * 1024 * 1024, 1)
                            print(f"\r  [{pct:5.1f}%] {mb_curr:.1f}/{mb_total:.1f} MB | {speed_mb:.2f} MB/s | Kalan: {int(eta_s)}s   ", end="", flush=True)
                        else:
                            mb_curr = current_downloaded / (1024 * 1024)
                            print(f"\r  {mb_curr:.1f} MB indirildi | {speed_mb:.2f} MB/s   ", end="", flush=True)
        
        # Rename part to final
        if os.path.exists(dest_path):
            os.remove(dest_path)
        os.rename(part_path, dest_path)
        print(f"\n✓ Başarıyla tamamlandı: {filename}")
        return True

    except Exception as e:
        print(f"\n❌ İndirme hatası: {e}")
        return False

def generate_scripts(items):
    found_items = [it for it in items if it.get('found')]
    
    # 1. Plain text list for IDM / JDownloader
    txt_path = "arsiv_indirme_linkleri.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        for it in found_items:
            f.write(f"https://tube.archivarix.net/api/videos/{it['old_video_id']}/file\n")
    print(f"✓ IDM / JDownloader için link listesi kaydedildi: {txt_path} ({len(found_items)} link)")

    # 2. Windows BAT file with curl.exe
    bat_path = "indir_tumunu_curl.bat"
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write("@echo off\n")
        f.write("chcp 65001 > nul\n")
        f.write('if not exist "arsivden indirilenler" mkdir "arsivden indirilenler"\n')
        f.write("echo Tarihin Arka Odasi - Arsiv Indirme Baslatiliyor...\n\n")
        
        for it in found_items:
            safe_topic = clean_filename(it.get('topic') or '')[:35]
            fname = clean_filename(f"[No {it['id']}] {it['date_tr']} - {safe_topic}.webm")
            url = f"https://tube.archivarix.net/api/videos/{it['old_video_id']}/file"
            f.write(f'echo [{it["id"]}/354] {it["date_tr"]} indiriliyor...\n')
            f.write(f'curl.exe -L -C - --retry 3 --retry-delay 2 -# "{url}" -o "arsivden indirilenler\\{fname}"\n\n')
        
        f.write('echo.\n')
        f.write('echo TUM INDIRMELER TAMAMLANDI!\n')
        f.write('pause\n')
    print(f"✓ Otomatik Windows toplu indirme betiği oluşturuldu: {bat_path}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tarihin Arka Odası Arşiv İndirici")
    parser.add_argument('--test', action='store_true', help="İlk 1 videoyu test amaçlı indir")
    parser.add_argument('--limit', type=int, default=None, help="Belirtilen sayıda video indir")
    parser.add_argument('--ep', type=int, default=None, help="Sadece belirtilen bölüm numarasını indir (örn. 199)")
    parser.add_argument('--all', action='store_true', help="Arşivde bulunan 144 videonun tamamını indir")
    parser.add_argument('--generate-scripts', action='store_true', help="curl.bat ve link listesi üret")

    args = parser.parse_args()

    items = load_archive_results()
    found_items = [it for it in items if it.get('found')]

    if not args.test and not args.limit and not args.ep and not args.all:
        generate_scripts(items)
        print(f"\nArşivde indirilebilir tam video sayısı: {len(found_items)}")
        print("Nasıl indirmek istersiniz?")
        print("  1. Python ile otomatik:  python arsiv_indirici.py --all")
        print("  2. Belirli bölüm indir:  python arsiv_indirici.py --ep 199")
        print("  3. Windows Batch (curl): indir_tumunu_curl.bat dosyasına çift tıklayın")
        print("  4. IDM / JDownloader:    arsiv_indirme_linkleri.txt dosyasını içe aktarın")
        sys.exit(0)

    if args.generate_scripts:
        generate_scripts(items)

    to_download = []
    if args.ep:
        to_download = [it for it in found_items if it['id'] == args.ep]
        if not to_download:
            print(f"No {args.ep} bölümü arşivde bulunamadı.")
            sys.exit(1)
    elif args.test:
        to_download = found_items[:1]
    elif args.limit:
        to_download = found_items[:args.limit]
    elif args.all:
        to_download = found_items

    print(f"\nToplam indirilecek video sayısı: {len(to_download)}")
    for i, it in enumerate(to_download, 1):
        print(f"\n--- [{i}/{len(to_download)}] ---")
        download_video(it)
