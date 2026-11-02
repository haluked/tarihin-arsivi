import os
import sys
import time
import subprocess
import re
import threading
import openpyxl
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

SOURCE_DIR = "arsivden indirilenler"
OUTPUT_DIR = "arsiv_optimize"
EXCEL_FILE = "bölümler_arsiv.xlsx"
FFMPEG = r"C:\Program Files\Kdenlive\bin\ffmpeg.exe"
NUM_WORKERS = 4  # 4 video eşzamanlı işlenecek (~4 kat hız!)

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("=" * 75)
print("   TARİHİN ARKA ODASI — 4x PARALEL HIZLANDIRILMIŞ SES RESTORASYONU")
print("=" * 75)
print(f"Kaynak Klasör : {os.path.abspath(SOURCE_DIR)}")
print(f"Hedef Klasör  : {os.path.abspath(OUTPUT_DIR)}")
print(f"Eşzamanlı İş  : {NUM_WORKERS} paralel worker")
print("İmza          : Encoded & Restored by haluked | https://github.com/haluked")
print("=" * 75)

# Excel Kataloğunu Belleğe Yükle
metadata_map = {}
if os.path.exists(EXCEL_FILE):
    try:
        wb = openpyxl.load_workbook(EXCEL_FILE, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0] is not None:
                prog_no = str(row[0]).strip()
                metadata_map[prog_no] = {
                    "no": prog_no,
                    "tarih": str(row[1] or "").strip(),
                    "konu": str(row[2] or "").strip(),
                    "konuk": str(row[3] or "Yok").strip()
                }
        print(f"--> Excel veritabanından {len(metadata_map)} bölümün metadatası yüklendi.")
    except Exception as e:
        print(f"--> Excel okuma hatası: {e}")

source_videos = sorted([
    f for f in os.listdir(SOURCE_DIR)
    if f.endswith(".webm") and not f.endswith(".aria2")
])

total_vids = len(source_videos)
completed_count = 0
mono_yapilan = 0
dengeli_yapilan = 0
hata_sayisi = 0
lock = threading.Lock()
start_time = time.time()

def check_is_right_channel_dead(filepath):
    try:
        cmd = [
            FFMPEG, "-ss", "00:15:00", "-t", "5", "-i", filepath,
            "-af", "astats=metadata=1:reset=1",
            "-f", "null", "-"
        ]
        res = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        out = res.stderr
        ch1 = re.search(r"Channel: 1.*?RMS level dB:\s+([-\w.]+)", out, re.DOTALL)
        ch2 = re.search(r"Channel: 2.*?RMS level dB:\s+([-\w.]+)", out, re.DOTALL)
        if ch1 and ch2:
            def p(s):
                if "-inf" in str(s).lower(): return -999.0
                try: return float(s)
                except: return -999.0
            r1, r2 = p(ch1.group(1)), p(ch2.group(1))
            if r2 < -60.0 or (r1 - r2) > 15.0:
                return True, r1, r2
            return False, r1, r2
    except:
        pass
    return False, 0.0, 0.0

def process_single_video(vid):
    global completed_count, mono_yapilan, dengeli_yapilan, hata_sayisi
    src_path = os.path.join(SOURCE_DIR, vid)
    base_name = os.path.splitext(vid)[0]
    
    no_match = re.search(r"\[No\s+(\d+)\]", vid)
    prog_no = no_match.group(1) if no_match else ""
    meta_info = metadata_map.get(prog_no, {})
    
    tarih = meta_info.get("tarih", "")
    konu = meta_info.get("konu", "")
    konuk = meta_info.get("konuk", "Yok")
    
    is_dead, r1, r2 = check_is_right_channel_dead(src_path)
    if is_dead:
        out_filename = f"{base_name} [mono] [opus 24kbps].mkv"
        af_rule = "pan=mono|c0=FL"
        etiket = f"🚨 SAĞ ÖLÜ ({r1:.1f}dB vs {r2:.1f}dB) -> Mono klon"
    else:
        out_filename = f"{base_name} [opus 24kbps].mkv"
        af_rule = None
        etiket = f"✅ DENGELİ STEREO ({r1:.1f}dB vs {r2:.1f}dB) -> Stereo"
        
    out_path = os.path.join(OUTPUT_DIR, out_filename)
    temp_path = out_path + ".tmp.mkv"
    
    # Zaten bitmişse atla
    if os.path.exists(out_path) and os.path.getsize(out_path) > 10 * 1024 * 1024:
        with lock:
            completed_count += 1
            if is_dead: mono_yapilan += 1
            else: dengeli_yapilan += 1
            print(f"[{completed_count}/{total_vids}] [ZATEN MEVCUT] {out_filename}")
        return
        
    doc_title = f"Tarihin Arka Odası - {vid.replace('.webm', '')}"
    doc_desc = f"Program: {prog_no} | Tarih: {tarih} | Konu: {konu} | Konuk: {konuk} | Düzenleme & Restorasyon: haluked"
    
    cmd = [
        FFMPEG, "-y",
        "-i", src_path,
        "-c:v", "copy"
    ]
    if af_rule:
        cmd.extend(["-af", af_rule])
    cmd.extend([
        "-c:a", "libopus", "-b:a", "24k",
        "-metadata", f"title={doc_title}",
        "-metadata", "artist=Tarihin Arka Odası",
        "-metadata", "album=Tarihin Arka Odası Arşivi",
        "-metadata", f"date={tarih}",
        "-metadata", "comment=Encoded & Restored by haluked | https://github.com/haluked",
        "-metadata", "encoded_by=haluked (https://github.com/haluked)",
        "-metadata", f"description={doc_desc}",
        temp_path
    ])
    
    t0 = time.time()
    try:
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        if res.returncode == 0 and os.path.exists(temp_path):
            os.replace(temp_path, out_path)
            elapsed = time.time() - t0
            src_sz = os.path.getsize(src_path) / (1024 * 1024)
            out_sz = os.path.getsize(out_path) / (1024 * 1024)
            with lock:
                completed_count += 1
                if is_dead: mono_yapilan += 1
                else: dengeli_yapilan += 1
                print(f"[{completed_count}/{total_vids}] [OK] {out_filename} ({elapsed:.1f} sn | {src_sz:.1f} MB -> {out_sz:.1f} MB) | {etiket}")
        else:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            with lock:
                hata_sayisi += 1
                print(f"[HATA] {vid} -> {res.stderr[:150]}")
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        with lock:
            hata_sayisi += 1
            print(f"[HATA] {vid} -> {e}")

print(f"\n[BAŞLADI] {total_vids} bölüm {NUM_WORKERS} eşzamanlı işlemci ile dönüştürülüyor...\n")

with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
    futures = [executor.submit(process_single_video, vid) for vid in source_videos]
    for future in as_completed(futures):
        pass

total_elapsed = (time.time() - start_time) / 60.0

summary_text = f"""======================================================================
TARİHİN ARKA ODASI — 4X PARALEL SES RESTORASYON RAPORU
======================================================================
Tamamlanma Zamanı           : {time.strftime('%Y-%m-%d %H:%M:%S')}
İmza                        : Encoded & Restored by haluked (https://github.com/haluked)
Toplam İncelenen Bölüm      : {total_vids}
Sağ Kanalı Bozuk ([mono])   : {mono_yapilan} bölüm
Zaten Dengeli Korunan       : {dengeli_yapilan} bölüm
Hata Alan                   : {hata_sayisi}
Toplam İşlem Süresi         : {total_elapsed:.1f} Dakika
Hedef Klasör                : {os.path.abspath(OUTPUT_DIR)}
======================================================================
"""

with open("SES_DONUSTURME_TAMAMLANDI.txt", "w", encoding="utf-8") as f:
    f.write(summary_text)

print("\n" + summary_text)

# Tüm işlemler bittiğinde sistemi yeniden başlat (reboot)
print("\n[BİLGİ] Tüm işlemler başarıyla bitti. Bilgisayar 60 saniye içinde yeniden başlatılıyor...")
os.system('shutdown /r /t 60 /c "Tarihin Arka Odasi tum ses restorasyonlari basariyla tamamlandi. Sistem yeniden baslatiliyor."')
