import openpyxl
import json
import re
import os
import sys

# 1. Load data from 'bölümler_arsiv.xlsx'
wb_source = openpyxl.load_workbook('bölümler_arsiv.xlsx', data_only=True)
ws_source = wb_source.active

MONTHS_MAP = {
    'Ocak': '01', 'Şubat': '02', 'Mart': '03', 'Nisan': '04',
    'Mayıs': '05', 'Haziran': '06', 'Temmuz': '07', 'Ağustos': '08',
    'Eylül': '09', 'Ekim': '10', 'Kasım': '11', 'Aralık': '12'
}

episodes = []

for r in range(2, ws_source.max_row + 1):
    no = ws_source.cell(r, 1).value
    date_str = str(ws_source.cell(r, 2).value or '').strip()
    topic = str(ws_source.cell(r, 3).value or '').strip()
    guest = str(ws_source.cell(r, 4).value or '').strip()
    note = str(ws_source.cell(r, 5).value or '').strip()
    yt_links_raw = str(ws_source.cell(r, 6).value or '').strip()
    arch_link = str(ws_source.cell(r, 7).value or '').strip()
    old_link = str(ws_source.cell(r, 8).value or '').strip()
    status_raw = str(ws_source.cell(r, 9).value or '').strip()

    if not no:
        continue

    # Extract year
    m_year = re.search(r'20\d\d', date_str)
    year = m_year.group(0) if m_year else "Diğer"

    # Clean links
    yt_links = []
    if yt_links_raw and yt_links_raw != '-':
        yt_links = [l.strip() for l in yt_links_raw.split() if l.strip().startswith('http')]

    has_yt = len(yt_links) > 0
    has_arch = arch_link.startswith('http')
    
    if has_yt:
        ep_type = 'yt'
        status_clean = 'YouTube'
    elif has_arch:
        ep_type = 'arch'
        status_clean = 'Web Arşivi (.webm)'
    else:
        ep_type = 'missing'
        status_clean = 'Eksik'

    episodes.append({
        'no': int(no),
        'date': date_str,
        'year': year,
        'topic': topic,
        'guest': guest,
        'note': note,
        'yt_links': yt_links,
        'has_yt': has_yt,
        'arch_link': arch_link if has_arch else None,
        'has_arch': has_arch,
        'old_link': old_link if (old_link and old_link != '-' and old_link != '???') else None,
        'type': ep_type,
        'status': status_clean
    })

print(f"Toplam bölüm yüklendi: {len(episodes)}")
yt_cnt = sum(1 for e in episodes if e['type'] == 'yt')
arch_cnt = sum(1 for e in episodes if e['type'] == 'arch')
missing_cnt = sum(1 for e in episodes if e['type'] == 'missing')
print(f"YouTube: {yt_cnt}, Arşiv: {arch_cnt}, Eksik: {missing_cnt}")

# Write to a clean JSON for reference
with open('arsiv_tum_bolumler.json', 'w', encoding='utf-8') as f:
    json.dump(episodes, f, ensure_ascii=False, indent=2)
print("arsiv_tum_bolumler.json kaydedildi.")
