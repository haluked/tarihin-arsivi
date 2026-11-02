import json
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

INPUT_JSON = "youtube_indirme_listesi.json"
OUTPUT_JSON = "youtube_analiz_sonuclari.json"

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    items = json.load(f)

print(f"Toplam incelenecek YouTube videosu: {len(items)}")
print("yt-dlp ile format, çözünürlük ve kodek taraması başlatılıyor (8 paralel worker)...\n")

results = []
lock = threading.Lock()
completed = 0
total = len(items)

def probe_video(item):
    global completed
    url = item["url"]
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        "--skip-download",
        "--socket-timeout", "10",
        url
    ]
    info = {
        "no": item.get("no"),
        "tarih": item.get("tarih"),
        "konu": item.get("konu"),
        "filename": item.get("filename"),
        "url": url,
        "durum": "Bilinmiyor",
        "title": "",
        "duration": 0,
        "has_av1": False,
        "has_vp9": False,
        "has_h264": False,
        "has_opus": False,
        "has_m4a": False,
        "best_video_codec": None,
        "max_resolution": None,
        "best_v_format_id": None,
        "best_a_format_id": None,
        "best_format_str": None,
        "formats_summary": []
    }
    
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            info["durum"] = "Aktif"
            info["title"] = data.get("title", "")
            info["duration"] = data.get("duration", 0)
            
            formats = data.get("formats", [])
            video_formats = []
            audio_formats = []
            
            for fmt in formats:
                vcodec = fmt.get("vcodec", "none")
                acodec = fmt.get("acodec", "none")
                fid = fmt.get("format_id")
                height = fmt.get("height") or 0
                width = fmt.get("width") or 0
                tbr = fmt.get("tbr") or 0
                filesize = fmt.get("filesize") or fmt.get("filesize_approx") or 0
                
                if vcodec != "none" and "none" not in vcodec.lower():
                    if "av01" in vcodec.lower(): info["has_av1"] = True
                    elif "vp9" in vcodec.lower() or "vp09" in vcodec.lower(): info["has_vp9"] = True
                    elif "avc" in vcodec.lower() or "h264" in vcodec.lower(): info["has_h264"] = True
                    video_formats.append((height, width, tbr, fid, vcodec, filesize))
                    
                if acodec != "none" and "none" not in acodec.lower():
                    if "opus" in acodec.lower(): info["has_opus"] = True
                    elif "mp4a" in acodec.lower() or "aac" in acodec.lower(): info["has_m4a"] = True
                    audio_formats.append((fmt.get("abr") or 0, fid, acodec, filesize))
            
            if video_formats:
                video_formats.sort(key=lambda x: (x[0], x[2]), reverse=True)
                best_v = video_formats[0]
                info["max_resolution"] = f"{best_v[1]}x{best_v[0]}"
                info["best_v_format_id"] = best_v[3]
                info["best_video_codec"] = best_v[4]
                
            if audio_formats:
                audio_formats.sort(key=lambda x: x[0], reverse=True)
                best_a = audio_formats[0]
                info["best_a_format_id"] = best_a[1]
                info["best_audio_codec"] = best_a[2]
                
        else:
            err = proc.stderr
            if "Video unavailable" in err or "Private video" in err or "This video has been removed" in err:
                info["durum"] = "Kaldırılmış / Erişilemez"
            else:
                info["durum"] = f"Hata: {err[:60].strip()}"
    except Exception as e:
        info["durum"] = f"Exception: {str(e)[:60]}"

    with lock:
        completed += 1
        results.append(info)
        status_icon = "✅" if info["durum"] == "Aktif" else "❌"
        res_str = info["max_resolution"] or "Yok"
        v_cod = (info["best_video_codec"] or "").split(".")[0]
        a_cod = "opus" if info["has_opus"] else ("aac" if info["has_m4a"] else "none")
        print(f"[{completed}/{total}] {status_icon} No {info['no']} -> {info['durum']} | Çöz: {res_str} | V:{v_cod} | A:{a_cod}")

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = [executor.submit(probe_video, item) for item in items]
    for future in as_completed(futures):
        pass

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\n" + "=" * 70)
print("                   YOUTUBE KODEK VE DURUM ÖZETİ")
print("=" * 70)
aktifler = [r for r in results if r["durum"] == "Aktif"]
pasifler = [r for r in results if r["durum"] != "Aktif"]
has_av1 = sum(1 for r in aktifler if r["has_av1"])
has_vp9 = sum(1 for r in aktifler if r["has_vp9"])
has_opus = sum(1 for r in aktifler if r["has_opus"])

res_dist = {}
for r in aktifler:
    res = r["max_resolution"] or "Bilinmiyor"
    res_dist[res] = res_dist.get(res, 0) + 1

print(f"Toplam Taranan Video      : {len(results)}")
print(f"Aktif Olanlar             : {len(aktifler)}")
print(f"Erişilemeyenler (Kayıp)   : {len(pasifler)}")
print(f"AV1 Desteği Olan          : {has_av1}")
print(f"VP9 Desteği Olan          : {has_vp9}")
print(f"Opus Desteği Olan         : {has_opus}")
print("\nÇözünürlük Dağılımı:")
for k, v in sorted(res_dist.items(), key=lambda x: x[1], reverse=True):
    print(f"  • {k}: {v} video")

if pasifler:
    print("\nErişilemeyen Videolar:")
    for p in pasifler:
        print(f"  • No {p['no']} ({p['tarih']}): {p['url']} [{p['durum']}]")
