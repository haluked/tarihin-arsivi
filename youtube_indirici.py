import json
import os
import sys
import subprocess
import time
import re

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

TARGET_DIR = "youtube indirilenler"
LIST_FILE = "youtube_indirme_listesi.json"
ARCHIVE_FILE = os.path.join(TARGET_DIR, "arsiv_tamamlananlar.txt")
SKIPPED_FILE = os.path.join(TARGET_DIR, "indirilemeyen_videolar.txt")

FFMPEG_EXE = r"C:\Program Files\Kdenlive\bin\ffmpeg.exe"
FFMPEG_DIR = r"C:\Program Files\Kdenlive\bin"

if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR, exist_ok=True)

if not os.path.exists(LIST_FILE):
    print(f"HATA: {LIST_FILE} bulunamadı!")
    sys.exit(1)

with open(LIST_FILE, "r", encoding="utf-8") as f:
    items = json.load(f)

# Daha önce indirilenleri oku
completed_urls = set()
if os.path.exists(ARCHIVE_FILE):
    with open(ARCHIVE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                completed_urls.add(line.split("\t")[0].strip())

total_count = len(items)

print("=" * 75)
print("   TARİHİN ARKA ODASI — GÜVENLİ YOUTUBE İNDİRİCİ & SES DÖNÜŞTÜRÜCÜ")
print("=" * 75)
print(f" * Toplam Video Sayısı    : {total_count}")
print(f" * Daha Önce Tamamlanan   : {len(completed_urls)}")
print(f" * Kalan Video Sayısı     : {total_count - len(completed_urls)}")
print(f" * Hedef Klasör           : {os.path.abspath(TARGET_DIR)}")
print(f" * İndirme Modu           : TEKLİ & GÜVENLİ (Sıfır Ban Koruması, -N 1)")
print(f" * Video Kodek Sırası     : AV1 ➔ VP9 ➔ H.264")
print(f" * Ses Standardı          : Opus 24 kbps (Mono/Stereo Dengeleme)")
print(f" * Çıktı Formatı          : Saf MKV (.mkv)")
print(f" * Dinlenme Molası        : Her bölüm sonrası 4 saniye")
print("=" * 75)
print()

def check_is_right_channel_dead(filepath):
    """Sağ kanal sağırlığını 2. dakikadaki 5 saniyelik kesitle test eder."""
    try:
        cmd = [
            FFMPEG_EXE, "-ss", "00:02:00", "-t", "5", "-i", filepath,
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
    except Exception:
        pass
    return False, 0.0, 0.0

success_count = 0
skip_count = 0
error_count = 0

for idx, item in enumerate(items, 1):
    url = item["url"]
    filename_base = item["filename"]
    
    # URL veya hedef dosya zaten varsa atla
    possible_names = [
        f"{filename_base} [opus 24kbps].mkv",
        f"{filename_base} [mono] [opus 24kbps].mkv",
        f"{filename_base}.mkv"
    ]
    already_done = url in completed_urls or any(
        os.path.exists(os.path.join(TARGET_DIR, name)) and os.path.getsize(os.path.join(TARGET_DIR, name)) > 10 * 1024 * 1024
        for name in possible_names
    )
    
    if already_done:
        print(f"[{idx}/{total_count}] [ATLANDI - ZATEN MEVCUT] {filename_base}")
        continue
        
    print(f"\n[{idx}/{total_count}] >>> İndiriliyor: {filename_base}")
    print(f"       URL: {url}")
    
    temp_prefix = f"__temp_dl_{idx}"
    temp_tmpl = os.path.join(TARGET_DIR, f"{temp_prefix}.%(ext)s")
    temp_target_mkv = os.path.join(TARGET_DIR, f"{temp_prefix}.mkv")
    
    # 1. Aşama: yt-dlp ile Tekli Güvenli İndirme
    cmd_dl = [
        "yt-dlp",
        "--ffmpeg-location", FFMPEG_DIR,
        "--no-playlist",
        "--continue",
        "--retries", "10",
        "--fragment-retries", "10",
        "--socket-timeout", "30",
        "-f", "bv*[vcodec^=av01]+ba/bv*[vcodec^=vp9]+ba/bv*[vcodec^=avc1]+ba/bv*+ba/b",
        "--merge-output-format", "mkv",
        "-o", temp_tmpl,
        url
    ]
    
    t_start = time.time()
    try:
        res = subprocess.run(cmd_dl)
    except KeyboardInterrupt:
        print("\n[DURDURULDU] İndirme kullanıcı tarafından güvenle duraklatıldı.")
        # Geçici part dosyasını temizleme, yt-dlp kaldığı yerden devam edebilir
        break
    except Exception as e:
        print(f"       [HATA] İndirme çalıştırılamadı: {e}")
        error_count += 1
        continue
        
    if res.returncode != 0 or not os.path.exists(temp_target_mkv):
        print(f"       [UYARI] Video indirilemedi veya YouTube'da erişilemez! (Kod: {res.returncode})")
        with open(SKIPPED_FILE, "a", encoding="utf-8") as sf:
            sf.write(f"{url}\t{filename_base}\tHata Kodu: {res.returncode}\n")
        error_count += 1
        time.sleep(2)
        continue
        
    dl_duration = time.time() - t_start
    raw_size_mb = os.path.getsize(temp_target_mkv) / (1024 * 1024)
    print(f"       [İNDİRME TAMAM] Ham Boyut: {raw_size_mb:.1f} MB (Süre: {dl_duration:.1f}s)")
    
    # 2. Aşama: Ses Analizi ve 24 kbps Opus'a Dönüştürme
    print(f"       [DÖNÜŞTÜRÜLÜYOR] Ses analizi ve Opus 24 kbps kodlaması yapılıyor...")
    is_dead, r1, r2 = check_is_right_channel_dead(temp_target_mkv)
    
    if is_dead:
        final_filename = f"{filename_base} [mono] [opus 24kbps].mkv"
        af_args = ["-af", "pan=mono|c0=FL"]
        print(f"       [SES MODU] 🚨 Sağ kanal sessiz ({r1:.1f}dB / {r2:.1f}dB) -> Mono dengelendi")
    else:
        final_filename = f"{filename_base} [opus 24kbps].mkv"
        af_args = []
        print(f"       [SES MODU] ✅ Stereo dengeli ({r1:.1f}dB / {r2:.1f}dB) -> Stereo Opus")
        
    final_output_path = os.path.join(TARGET_DIR, final_filename)
    final_temp_path = os.path.join(TARGET_DIR, f"__proc_{idx}.mkv")
    
    cmd_ffmpeg = [
        FFMPEG_EXE, "-y",
        "-i", temp_target_mkv,
        "-c:v", "copy"
    ] + af_args + [
        "-c:a", "libopus", "-b:a", "24k",
        final_temp_path
    ]
    
    t_ff_start = time.time()
    try:
        ff_res = subprocess.run(cmd_ffmpeg, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"       [HATA] FFmpeg çalışırken hata: {e}")
        ff_res = None
        
    if ff_res and ff_res.returncode == 0 and os.path.exists(final_temp_path) and os.path.getsize(final_temp_path) > 1024 * 1024:
        os.replace(final_temp_path, final_output_path)
        # Ham geçici dosyayı sil
        try:
            os.remove(temp_target_mkv)
        except Exception:
            pass
            
        ff_duration = time.time() - t_ff_start
        final_size_mb = os.path.getsize(final_output_path) / (1024 * 1024)
        print(f"       [HAZIR] {final_filename} ({final_size_mb:.1f} MB, Dönüşüm: {ff_duration:.1f}s)")
        
        # Tamamlananlara kaydet
        with open(ARCHIVE_FILE, "a", encoding="utf-8") as af:
            af.write(f"{url}\t{final_filename}\n")
        completed_urls.add(url)
        success_count += 1
    else:
        print("       [HATA] FFmpeg ses dönüştürmesi başarısız oldu!")
        error_count += 1
        
    # 3. Aşama: Güvenlik Molası (Sıfır Ban)
    print("       [GÜVENLİK MOLASI] YouTube sunucusuna 4 saniye nefes payı veriliyor...")
    time.sleep(4)

print("\n" + "=" * 75)
print("   İŞLEM TAMAMLANDI VEYA DURAKLATILDI")
print("=" * 75)
print(f" * Bu oturumda tamamlanan : {success_count}")
print(f" * Toplam tamamlanan       : {len(completed_urls)} / {total_count}")
print(f" * Karşılaşılan hata      : {error_count}")
print("=" * 75)
