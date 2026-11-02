import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

def to_ascii_tr(text):
    tr_map = {'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'I', 'ö': 'o', 'Ö': 'O', 'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'}
    for k, v in tr_map.items():
        text = text.replace(k, v)
    return text

def clean_filename(name):
    name = to_ascii_tr(name)
    cleaned = re.sub(r'[\\/*?:"<>|\']', '', name)
    return re.sub(r'\s+', ' ', cleaned).strip()

with open('tam_arsiv_tarama_sonuclari.json', 'r', encoding='utf-8') as f:
    items = json.load(f)

found_items = [it for it in items if it.get('found')]
print(f"Toplam indirilecek arşiv bölümü: {len(found_items)}")

lines = []
for it in found_items:
    p_no = it['id']
    date_tr = it['date_tr']
    topic = it.get('topic') or 'Konu Belirtilmedi'
    vid = it['old_video_id']
    url = it.get('download_url') or f"https://web.archive.org/web/2oe_/http://wayback-fakeurl.archive.org/yt/{vid}"
    
    safe_topic = clean_filename(topic)[:40]
    out_name = f"[No {p_no}] {date_tr} - {safe_topic}.webm"
    
    lines.append(url)
    lines.append("  dir=arsivden indirilenler")
    lines.append(f"  out={out_name}")
    lines.append("")

with open('aria2_indirme_listesi.txt', 'w', encoding='utf-8') as f:
    f.write("\n".join(lines))

print(f"✓ aria2_indirme_listesi.txt oluşturuldu ({len(found_items)} video)")

# Also create a batch launcher: arsivi_indir_aria2.bat
bat_content = """@echo off
chcp 65001 > nul
title Tarihin Arka Odasi - Arsiv Indirici (Aria2)
cls
echo ======================================================================
echo    TARİHİN ARKA ODASI — ARŞİV İNDİRİCİ (Aria2 Resilient Downloader)
echo ======================================================================
echo  * Toplam 144 Arşiv Videosu İndirilecek (arsivden indirilenler klasorune)
echo  * Baglanti kopsa veya kapatsaniz bile kaldigi megabayttan devam eder!
echo  * Indirmeyi durdurmak icin istediginiz zaman pencereyi kapatabilirsiniz.
echo ======================================================================
echo.

if not exist "arsivden indirilenler" mkdir "arsivden indirilenler"

aria2c.exe -c -s 1 -x 1 --file-allocation=none --max-concurrent-downloads=1 --summary-interval=5 --console-log-level=warn --input-file=aria2_indirme_listesi.txt

echo.
echo ======================================================================
echo   İNDİRME İŞLEMİ TAMAMLANDI VEYA DURAKLATILDI.
echo ======================================================================
pause
"""

with open('arsivi_indir_aria2.bat', 'w', encoding='utf-8') as f:
    f.write(bat_content)

print("✓ arsivi_indir_aria2.bat oluşturuldu.")
