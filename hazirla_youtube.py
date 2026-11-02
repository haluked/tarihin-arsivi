import openpyxl
import re
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

wb = openpyxl.load_workbook('bölümler_arsiv.xlsx')
ws = wb.active

def clean_filename(s):
    if not s:
        return ''
    s = str(s).strip()
    s = re.sub(r'[\\/*?:"<>|]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

items = []
for row in ws.iter_rows(min_row=2, values_only=True):
    prog_no = str(row[0]).strip() if row[0] is not None else ''
    tarih = clean_filename(row[1])
    konu = clean_filename(row[2])
    yt_cell = str(row[5] or '')
    if yt_cell and yt_cell != 'None':
        urls = re.findall(r'https?://(?:www\.)?youtu(?:be\.com/watch\?v=|\.be/)([\w\-]+)', yt_cell)
        if urls:
            if len(urls) == 1:
                items.append({
                    'no': prog_no,
                    'tarih': tarih,
                    'konu': konu,
                    'url': f'https://www.youtube.com/watch?v={urls[0]}',
                    'filename': f'[No {prog_no}] {tarih} - {konu}'
                })
            else:
                for idx, vid in enumerate(urls, 1):
                    items.append({
                        'no': prog_no,
                        'tarih': tarih,
                        'konu': konu,
                        'url': f'https://www.youtube.com/watch?v={vid}',
                        'filename': f'[No {prog_no} Part {idx}] {tarih} - {konu}'
                    })

print(f'Hazırlanan toplam YouTube video sayısı: {len(items)}')

with open('youtube_indirme_listesi.json', 'w', encoding='utf-8') as f:
    json.dump(items, f, ensure_ascii=False, indent=2)

print('youtube_indirme_listesi.json başarıyla oluşturuldu.')
