import sys
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import json
import re
import os
import html

sys.stdout.reconfigure(encoding='utf-8')

print("1. Veriler bölümler_arsiv.xlsx dosyasından okunuyor...")

wb_src = openpyxl.load_workbook('bölümler_arsiv.xlsx', data_only=True)
ws_src = wb_src.active

episodes = []

for r in range(2, ws_src.max_row + 1):
    no_val = ws_src.cell(r, 1).value
    if not no_val:
        continue
    try:
        no = int(no_val)
    except:
        no = str(no_val).strip()

    date_str = str(ws_src.cell(r, 2).value or '').strip()
    topic = str(ws_src.cell(r, 3).value or '').strip()
    guest = str(ws_src.cell(r, 4).value or '').strip()
    note = str(ws_src.cell(r, 5).value or '').strip()
    yt_raw = str(ws_src.cell(r, 6).value or '').strip()
    arch_raw = str(ws_src.cell(r, 7).value or '').strip()
    old_raw = str(ws_src.cell(r, 8).value or '').strip()
    status_raw = str(ws_src.cell(r, 9).value or '').strip()

    # Yıl bulma
    m_yr = re.search(r'20\d\d', date_str)
    year = m_yr.group(0) if m_yr else "2008"

    # Linkler
    yt_links = []
    if yt_raw and yt_raw != '-':
        for part in yt_raw.split():
            part = part.strip()
            if part.startswith('http'):
                yt_links.append(part)

    has_yt = len(yt_links) > 0
    has_arch = arch_raw.startswith('http')
    arch_link = arch_raw if has_arch else None
    
    old_link = None
    if old_raw and old_raw != '-' and old_raw != '???':
        old_link = old_raw

    # Video id bulma
    video_id = None
    if has_yt:
        m_vid = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', yt_links[0])
        if m_vid:
            video_id = m_vid.group(1)
    elif old_link:
        m_vid = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', old_link)
        if m_vid:
            video_id = m_vid.group(1)

    if has_yt:
        ep_type = 'yt'
        status_label = 'YouTube'
    elif has_arch:
        ep_type = 'arch'
        status_label = 'Web Arşivi (.webm)'
    else:
        ep_type = 'missing'
        status_label = 'Eksik'

    episodes.append({
        'no': no,
        'date': date_str,
        'year': year,
        'topic': topic,
        'guest': guest,
        'note': note,
        'yt_links': yt_links,
        'has_yt': has_yt,
        'arch_link': arch_link,
        'has_arch': has_arch,
        'old_link': old_link,
        'video_id': video_id,
        'type': ep_type,
        'status': status_label
    })

print(f"Toplam {len(episodes)} bölüm ayrıştırıldı.")
yt_count = sum(1 for e in episodes if e['type'] == 'yt')
arch_count = sum(1 for e in episodes if e['type'] == 'arch')
missing_count = sum(1 for e in episodes if e['type'] == 'missing')
total_count = len(episodes)
ready_ratio = f"{((yt_count + arch_count) / total_count * 100):.1f}%"

print(f"İstatistik: Toplam={total_count}, YouTube={yt_count}, Arşiv={arch_count}, Eksik={missing_count}, Başarı={ready_ratio}")

# ==========================================================
# 2. GENERATE SELF-CONTAINED HTML (index.html & arsiv_paneli.html)
# ==========================================================
print("2. Self-contained HTML dosyaları üretiliyor...")

rows_html = []
for ep in episodes:
    # Arama dizgesi
    search_haystack = html.escape(f"{ep['no']} {ep['date']} {ep['topic']} {ep['guest']} {ep['note']} {ep['status']}".lower())

    # Butonlar
    buttons_cell = []
    direct_links_cell = []

    if ep['has_yt']:
        # YouTube ana izle butonu
        main_yt = ep['yt_links'][0]
        buttons_cell.append(f'<a href="{main_yt}" target="_blank" rel="noopener noreferrer" class="btn-play btn-yt" title="YouTube üzerinden izle">▶ YouTube</a>')
        
        # Parça linkleri
        if len(ep['yt_links']) == 1:
            direct_links_cell.append(f'<a href="{main_yt}" target="_blank" rel="noopener noreferrer" class="link-pill link-pill-yt">YouTube</a>')
        else:
            for idx, yl in enumerate(ep['yt_links']):
                direct_links_cell.append(f'<a href="{yl}" target="_blank" rel="noopener noreferrer" class="link-pill link-pill-yt">Part {idx+1}</a>')

        status_badge = '<span class="status-badge badge-yt">🔴 YouTube</span>'
        row_class = 'row-yt'

    elif ep['has_arch']:
        arch_url = ep['arch_link']
        modal_title = f"{ep['no']} - {ep['date']} | {ep['topic']}".replace("'", "\\'")
        # Arşiv oynat butonu (yeni sekmede doğrudan video stream açar)
        buttons_cell.append(f'<a href="{arch_url}" target="_blank" rel="noopener noreferrer" class="btn-play btn-arch" title="Arşivden doğrudan .webm videosunu oynat / indir">🏛️ Arşivden Oynat</a>')
        # Modalda oynat seçeneği
        buttons_cell.append(f'<button type="button" class="btn-preview" onclick="openPlayerModal(\'{arch_url}\', \'{modal_title}\', \'video\')" title="Sayfa içi modal oynatıcıda izle">📺 Modalda İzle</button>')

        direct_links_cell.append(f'<a href="{arch_url}" target="_blank" rel="noopener noreferrer" class="link-pill link-pill-arch">Direct .webm</a>')
        if ep['old_link']:
            old_url = ep['old_link']
            direct_links_cell.append(f'<a href="{old_url}" target="_blank" rel="noopener noreferrer" class="link-pill link-pill-old" title="Eski / Orijinal Silinmiş YouTube Linki">Eski YT Linki</a>')

        status_badge = '<span class="status-badge badge-arch">🟢 Arşiv (.webm)</span>'
        row_class = 'row-arch'

    else:
        buttons_cell.append('<span class="btn-missing">⚪ Eksik (15\'ten biri)</span>')
        status_badge = '<span class="status-badge badge-missing">⚪ Eksik</span>'
        direct_links_cell.append('<span class="text-muted">Bağlantı bulunamadı</span>')
        row_class = 'row-missing'

    btn_html = "".join(buttons_cell)
    links_html = "".join(direct_links_cell)

    topic_safe = html.escape(ep['topic']) if ep['topic'] else '<span class="text-muted">-</span>'
    guest_safe = html.escape(ep['guest']) if ep['guest'] else '<span class="text-muted">-</span>'
    note_safe = html.escape(ep['note']) if ep['note'] else ''

    row_code = f'''<tr class="{row_class}" id="row_{ep['no']}" data-no="{ep['no']}" data-year="{ep['year']}" data-type="{ep['type']}" data-search="{search_haystack}">
    <td class="center cell-actions">{btn_html}</td>
    <td class="center cell-no"><strong>{ep['no']}</strong></td>
    <td class="cell-date">{html.escape(ep['date'])}</td>
    <td class="cell-topic">{topic_safe}</td>
    <td class="cell-guest">{guest_safe}</td>
    <td class="cell-note">{note_safe}</td>
    <td class="center cell-status">{status_badge}</td>
    <td class="cell-links"><div class="links-wrap">{links_html}</div></td>
</tr>'''
    rows_html.append(row_code)

all_rows_str = "\n".join(rows_html)

# Self-contained HTML Template
html_content = f'''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tarihin Arka Odası — Eksiksiz Bölüm Arşivi (2008 – 2015)</title>
    <meta name="description" content="Tarihin Arka Odası programının (2008-2015) 354 bölümünün tamamını içeren, YouTube ve Web Arşivi (.webm) doğrudan oynatma bağlantılarına sahip interaktif arşiv kataloğu.">
    <style>
        :root {{
            --bg-body: #f8fafc;
            --bg-card: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #cbd5e1;
            --primary: #1e3a8a;
            --primary-hover: #1e40af;
            --yt-red: #dc2626;
            --yt-bg: #fef2f2;
            --yt-border: #fecaca;
            --arch-green: #16a34a;
            --arch-bg: #f0fdf4;
            --arch-border: #bbf7d0;
            --missing-bg: #f1f5f9;
            --missing-text: #64748b;
            --font-stack: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: var(--font-stack);
            font-size: 13px;
            background: var(--bg-body);
            color: var(--text-main);
            line-height: 1.4;
            padding: 12px 16px 40px 16px;
        }}

        .container {{
            max-width: 1540px;
            margin: 0 auto;
        }}

        /* Header */
        header {{
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
            color: #ffffff;
            padding: 20px 24px;
            border-radius: 8px;
            margin-bottom: 12px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .header-title h1 {{
            font-size: 20px;
            font-weight: 700;
            letter-spacing: -0.02em;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .header-title p {{
            font-size: 13px;
            color: #cbd5e1;
            margin-top: 4px;
        }}

        .header-stats {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .stat-card {{
            background: rgba(255, 255, 255, 0.12);
            backdrop-filter: blur(4px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            padding: 6px 14px;
            border-radius: 6px;
            text-align: center;
        }}

        .stat-card .num {{
            font-size: 18px;
            font-weight: 800;
            line-height: 1.1;
        }}

        .stat-card .lbl {{
            font-size: 10.5px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #e2e8f0;
        }}

        /* Controls / Toolbar */
        .toolbar {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 10px 14px;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
            box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }}

        .search-box {{
            flex: 1;
            min-width: 220px;
            padding: 7px 12px;
            font-size: 13px;
            border: 1px solid var(--border-color);
            border-radius: 5px;
            background: #fff;
            color: var(--text-main);
            outline: none;
            transition: border-color 0.15s;
        }}

        .search-box:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(30, 58, 138, 0.15);
        }}

        .select-filter {{
            padding: 7px 10px;
            font-size: 13px;
            border: 1px solid var(--border-color);
            border-radius: 5px;
            background: #fff;
            color: var(--text-main);
            cursor: pointer;
            outline: none;
        }}

        .filter-btn-group {{
            display: inline-flex;
            gap: 4px;
            flex-wrap: wrap;
        }}

        .btn-tab {{
            padding: 6px 11px;
            font-size: 12px;
            font-weight: 600;
            border: 1px solid var(--border-color);
            background: #f1f5f9;
            color: #334155;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
            user-select: none;
        }}

        .btn-tab:hover {{
            background: #e2e8f0;
        }}

        .btn-tab.active {{
            background: var(--primary);
            color: #ffffff;
            border-color: var(--primary);
        }}

        .btn-toggle-missing {{
            background: #fff1f2;
            color: #be123c;
            border: 1px solid #fda4af;
            font-weight: 600;
            padding: 6px 11px;
            font-size: 12px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s;
        }}

        .btn-toggle-missing:hover {{
            background: #ffe4e6;
        }}

        .btn-toggle-missing.active {{
            background: #e11d48;
            color: #ffffff;
            border-color: #be123c;
        }}

        .filter-counter {{
            margin-left: auto;
            font-size: 12px;
            font-weight: 600;
            color: var(--text-muted);
        }}

        /* Table */
        .table-responsive {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            overflow-x: auto;
            box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 12px;
        }}

        th {{
            background: #1e293b;
            color: #f8fafc;
            font-weight: 600;
            padding: 8px 10px;
            border-bottom: 2px solid #0f172a;
            position: sticky;
            top: 0;
            z-index: 10;
            font-size: 11.5px;
            letter-spacing: 0.02em;
        }}

        th.center, td.center {{
            text-align: center;
        }}

        td {{
            padding: 6px 9px;
            border-bottom: 1px solid #e2e8f0;
            vertical-align: middle;
        }}

        tbody tr:hover {{
            background-color: #f1f5f9 !important;
        }}

        tbody tr.row-yt {{
            background: #ffffff;
        }}

        tbody tr.row-arch {{
            background: #f8fdf9;
        }}

        tbody tr.row-missing {{
            background: #fbfbfb;
            color: #94a3b8;
        }}

        tr.hidden-row {{
            display: none !important;
        }}

        .cell-actions {{
            white-space: nowrap;
            width: 170px;
        }}

        .cell-no {{
            width: 44px;
            font-size: 12.5px;
            color: #475569;
        }}

        .cell-date {{
            white-space: nowrap;
            font-weight: 600;
            color: #1e293b;
            width: 105px;
        }}

        .cell-topic {{
            font-weight: 600;
            color: #0f172a;
            max-width: 260px;
        }}

        .cell-guest {{
            color: #334155;
            max-width: 180px;
        }}

        .cell-note {{
            color: #64748b;
            font-size: 11px;
            max-width: 150px;
        }}

        .cell-status {{
            width: 105px;
        }}

        .cell-links {{
            min-width: 160px;
        }}

        /* Action Buttons */
        .btn-play {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11.5px;
            font-weight: 700;
            text-decoration: none;
            transition: all 0.15s;
            cursor: pointer;
            margin-right: 4px;
            white-space: nowrap;
        }}

        .btn-yt {{
            background: #fee2e2;
            color: #b91c1c;
            border: 1px solid #fca5a5;
        }}

        .btn-yt:hover {{
            background: #dc2626;
            color: #ffffff;
            border-color: #b91c1c;
        }}

        .btn-arch {{
            background: #dcfce7;
            color: #15803d;
            border: 1px solid #86efac;
        }}

        .btn-arch:hover {{
            background: #16a34a;
            color: #ffffff;
            border-color: #15803d;
        }}

        .btn-preview {{
            display: inline-flex;
            align-items: center;
            gap: 3px;
            padding: 3px 6px;
            border-radius: 3px;
            font-size: 10.5px;
            font-weight: 600;
            background: #e0f2fe;
            color: #0369a1;
            border: 1px solid #7dd3fc;
            cursor: pointer;
            transition: all 0.15s;
            white-space: nowrap;
        }}

        .btn-preview:hover {{
            background: #0284c7;
            color: #ffffff;
        }}

        .btn-missing {{
            display: inline-block;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 600;
            color: #94a3b8;
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
        }}

        /* Badges */
        .status-badge {{
            display: inline-block;
            padding: 2px 7px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
        }}

        .badge-yt {{
            background: #fef2f2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }}

        .badge-arch {{
            background: #f0fdf4;
            color: #166534;
            border: 1px solid #bbf7d0;
        }}

        .badge-missing {{
            background: #f8fafc;
            color: #64748b;
            border: 1px solid #e2e8f0;
        }}

        /* Links wrap */
        .links-wrap {{
            display: flex;
            align-items: center;
            gap: 4px;
            flex-wrap: wrap;
        }}

        .link-pill {{
            font-size: 10.5px;
            padding: 2px 6px;
            border-radius: 3px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            transition: all 0.15s;
            white-space: nowrap;
        }}

        .link-pill-yt {{
            background: #fee2e2;
            color: #b91c1c;
            border: 1px solid #fca5a5;
        }}

        .link-pill-yt:hover {{
            background: #ef4444;
            color: #fff;
        }}

        .link-pill-arch {{
            background: #dcfce7;
            color: #15803d;
            border: 1px solid #86efac;
            font-weight: 600;
        }}

        .link-pill-arch:hover {{
            background: #22c55e;
            color: #fff;
        }}

        .link-pill-old {{
            background: #f1f5f9;
            color: #475569;
            border: 1px solid #cbd5e1;
            font-size: 10px;
        }}

        .link-pill-old:hover {{
            background: #cbd5e1;
            color: #0f172a;
        }}

        .text-muted {{
            color: #94a3b8;
            font-style: italic;
        }}

        /* Video Modal */
        .modal-overlay {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.85);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            padding: 20px;
        }}

        .modal-overlay.active {{
            display: flex;
        }}

        .modal-content {{
            background: #0f172a;
            border-radius: 8px;
            width: 100%;
            max-width: 900px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            display: flex;
            flex-direction: column;
        }}

        .modal-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 16px;
            background: #1e293b;
            color: #fff;
            border-bottom: 1px solid #334155;
        }}

        .modal-header h3 {{
            font-size: 14px;
            font-weight: 600;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .btn-modal-close {{
            background: transparent;
            border: none;
            color: #94a3b8;
            font-size: 20px;
            cursor: pointer;
            line-height: 1;
            padding: 2px 6px;
            border-radius: 4px;
        }}

        .btn-modal-close:hover {{
            color: #fff;
            background: #334155;
        }}

        .modal-body {{
            position: relative;
            padding-bottom: 56.25%; /* 16:9 aspect ratio */
            height: 0;
            background: #000;
        }}

        .modal-body video, .modal-body iframe {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            border: 0;
        }}

        .modal-footer {{
            padding: 8px 16px;
            background: #1e293b;
            color: #cbd5e1;
            font-size: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .modal-footer a {{
            color: #38bdf8;
            text-decoration: underline;
        }}

        @media (max-width: 768px) {{
            body {{
                padding: 6px;
            }}
            header {{
                padding: 14px;
            }}
            .header-title h1 {{
                font-size: 17px;
            }}
            .toolbar {{
                padding: 8px;
            }}
            .search-box {{
                width: 100%;
                min-width: 100%;
            }}
            .filter-counter {{
                width: 100%;
                margin-left: 0;
                margin-top: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <header>
            <div class="header-title">
                <h1>🏛️ Tarihin Arka Odası — Eksiksiz Bölüm Arşivi</h1>
                <p>Murat Bardakçı, Erhan Afyoncu, Pelin Batu & Nurhan Atasoy • Kanal 1 & Habertürk (2008 – 2015)</p>
            </div>
            <div class="header-stats">
                <div class="stat-card">
                    <div class="num">{total_count}</div>
                    <div class="lbl">Toplam Bölüm</div>
                </div>
                <div class="stat-card" style="border-color: rgba(239, 68, 68, 0.4);">
                    <div class="num" style="color: #fca5a5;">{yt_count}</div>
                    <div class="lbl">YouTube</div>
                </div>
                <div class="stat-card" style="border-color: rgba(34, 197, 94, 0.4);">
                    <div class="num" style="color: #86efac;">{arch_count}</div>
                    <div class="lbl">Arşiv (.webm)</div>
                </div>
                <div class="stat-card" style="border-color: rgba(148, 163, 184, 0.4);">
                    <div class="num" style="color: #cbd5e1;">{missing_count}</div>
                    <div class="lbl">Kalan Eksik</div>
                </div>
                <div class="stat-card" style="background: rgba(34, 197, 94, 0.2); border-color: rgba(34, 197, 94, 0.6);">
                    <div class="num" style="color: #86efac;">{ready_ratio}</div>
                    <div class="lbl">Erişilebilirlik</div>
                </div>
            </div>
        </header>

        <!-- Toolbar -->
        <div class="toolbar">
            <input type="text" id="searchInput" class="search-box" placeholder="🔍 Bölüm ara (konu, tarih, konuk, numara, not)...">

            <select id="yearSelect" class="select-filter">
                <option value="ALL">Tüm Yıllar (2008 - 2015)</option>
                <option value="2008">2008</option>
                <option value="2009">2009</option>
                <option value="2010">2010</option>
                <option value="2011">2011</option>
                <option value="2012">2012</option>
                <option value="2013">2013</option>
                <option value="2014">2014</option>
                <option value="2015">2015</option>
            </select>

            <div class="filter-btn-group">
                <button class="btn-tab active" data-filter="ALL">Tümü ({total_count})</button>
                <button class="btn-tab" data-filter="yt">🔴 YouTube ({yt_count})</button>
                <button class="btn-tab" data-filter="arch">🟢 Web Arşivi ({arch_count})</button>
                <button class="btn-tab" data-filter="missing">⚪ Eksikler ({missing_count})</button>
            </div>

            <button class="btn-toggle-missing" id="btnToggleMissing" onclick="toggleMissingOnly()">
                👁️ Sadece Eksikleri Göster
            </button>

            <div class="filter-counter" id="filterCounter">
                Gösterilen: <strong>{total_count}</strong> / {total_count}
            </div>
        </div>

        <!-- Table -->
        <div class="table-responsive">
            <table id="episodesTable">
                <thead>
                    <tr>
                        <th class="center" style="width: 165px;">Hemen İzle / Oynat</th>
                        <th class="center" style="width: 44px;">No</th>
                        <th style="width: 105px;">Tarih</th>
                        <th style="width: 250px;">Bölüm Konusu</th>
                        <th style="width: 170px;">Konuklar</th>
                        <th style="width: 140px;">Not</th>
                        <th class="center" style="width: 110px;">Durum</th>
                        <th style="min-width: 180px;">Doğrudan Bağlantılar</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
{all_rows_str}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Video Modal Player -->
    <div id="videoModal" class="modal-overlay" onclick="handleModalOverlayClick(event)">
        <div class="modal-content" onclick="event.stopPropagation()">
            <div class="modal-header">
                <h3 id="modalTitle">Video Oynatıcı</h3>
                <button class="btn-modal-close" onclick="closePlayerModal()">&times;</button>
            </div>
            <div class="modal-body" id="modalMediaContainer">
                <!-- Video or Iframe inserted dynamically -->
            </div>
            <div class="modal-footer">
                <span id="modalFooterNote">Tarayıcı içi video oynatılıyor</span>
                <a id="modalExternalLink" href="#" target="_blank" rel="noopener noreferrer">Yeni Sekmede Aç ↗</a>
            </div>
        </div>
    </div>

    <script>
        let curFilter = 'ALL';
        let curYear = 'ALL';
        let curSearch = '';
        let missingOnly = false;

        const tableBody = document.getElementById('tableBody');
        const rows = Array.from(tableBody.querySelectorAll('tr'));
        const counterEl = document.getElementById('filterCounter');
        const totalRows = rows.length;

        function applyFilter() {{
            let visibleCount = 0;

            rows.forEach(row => {{
                const rowType = row.getAttribute('data-type');
                const rowYear = row.getAttribute('data-year');
                const searchData = row.getAttribute('data-search') || '';

                let match = true;

                if (missingOnly && rowType !== 'missing') {{
                    match = false;
                }}

                if (curFilter !== 'ALL' && rowType !== curFilter) {{
                    match = false;
                }}

                if (curYear !== 'ALL' && rowYear !== curYear) {{
                    match = false;
                }}

                if (curSearch && !searchData.includes(curSearch)) {{
                    match = false;
                }}

                if (match) {{
                    row.classList.remove('hidden-row');
                    visibleCount++;
                }} else {{
                    row.classList.add('hidden-row');
                }}
            }});

            counterEl.innerHTML = `Gösterilen: <strong>${{visibleCount}}</strong> / ${{totalRows}}`;
        }}

        // Search input
        document.getElementById('searchInput').addEventListener('input', (e) => {{
            curSearch = e.target.value.trim().toLowerCase();
            applyFilter();
        }});

        // Year select
        document.getElementById('yearSelect').addEventListener('change', (e) => {{
            curYear = e.target.value;
            applyFilter();
        }});

        // Filter tabs
        document.querySelectorAll('.btn-tab').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.btn-tab').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                curFilter = btn.getAttribute('data-filter');
                applyFilter();
            }});
        }});

        // Toggle Missing Only
        function toggleMissingOnly() {{
            missingOnly = !missingOnly;
            const btn = document.getElementById('btnToggleMissing');
            if (missingOnly) {{
                btn.classList.add('active');
                btn.innerHTML = '✓ Sadece Eksikler Açık (Tıkla ve Sıfırla)';
            }} else {{
                btn.classList.remove('active');
                btn.innerHTML = '👁️ Sadece Eksikleri Göster';
            }}
            applyFilter();
        }}

        // Modal Video Player
        const modal = document.getElementById('videoModal');
        const modalContainer = document.getElementById('modalMediaContainer');
        const modalTitle = document.getElementById('modalTitle');
        const modalExtLink = document.getElementById('modalExternalLink');

        function openPlayerModal(url, title, type) {{
            modalTitle.innerText = title;
            modalExtLink.href = url;
            modalContainer.innerHTML = '';

            if (type === 'video') {{
                const videoEl = document.createElement('video');
                videoEl.controls = true;
                videoEl.autoplay = true;
                videoEl.src = url;
                modalContainer.appendChild(videoEl);
            }} else if (type === 'iframe') {{
                const iframe = document.createElement('iframe');
                iframe.src = url;
                iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
                iframe.allowFullscreen = true;
                modalContainer.appendChild(iframe);
            }}

            modal.classList.add('active');
        }}

        function closePlayerModal() {{
            modal.classList.remove('active');
            modalContainer.innerHTML = '';
        }}

        function handleModalOverlayClick(e) {{
            if (e.target === modal) {{
                closePlayerModal();
            }}
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape' && modal.classList.contains('active')) {{
                closePlayerModal();
            }}
        }});
    </script>
</body>
</html>
'''

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("✓ index.html oluşturuldu (GitHub Pages için hazır)")

with open('arsiv_paneli.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("✓ arsiv_paneli.html güncellendi")

# ==========================================================
# 3. GENERATE STYLED EXCEL (Tarihin_Arka_Odasi_Tam_Arsiv.xlsx & bölümler.xlsx)
# ==========================================================
print("3. Şık Excel dosyaları üretiliyor...")

wb_out = openpyxl.Workbook()
ws_out = wb_out.active
ws_out.title = "Tarihin Arka Odası - Tam Arşiv"

# Başlık satırları
headers = [
    "Prog. No", "Tarih", "Yıl", "Konu", "Konuk", "Not / Açıklama",
    "Durum", "YouTube İzleme Linki", "Arşivden Oynatma Linki (.webm)", "Eski / Referans Linki"
]

header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

thin_border_side = Side(border_style="thin", color="CBD5E1")
thin_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

fill_yt = PatternFill(start_color="FEF2F2", end_color="FEF2F2", fill_type="solid")
fill_arch = PatternFill(start_color="F0FDF4", end_color="F0FDF4", fill_type="solid")
fill_missing = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")

font_yt_badge = Font(name="Calibri", size=10, bold=True, color="991B1B")
font_arch_badge = Font(name="Calibri", size=10, bold=True, color="166534")
font_missing_badge = Font(name="Calibri", size=10, bold=True, color="64748B")

font_regular = Font(name="Calibri", size=10, color="0F172A")
font_bold = Font(name="Calibri", size=10, bold=True, color="0F172A")
font_link = Font(name="Calibri", size=10, color="1D4ED8", underline="single")
font_arch_link = Font(name="Calibri", size=10, color="15803D", underline="single")

ws_out.row_dimensions[1].height = 26

for col_idx, h_text in enumerate(headers, start=1):
    cell = ws_out.cell(row=1, column=col_idx, value=h_text)
    cell.fill = header_fill
    cell.font = header_font
    cell.alignment = header_alignment
    cell.border = thin_border

for row_idx, ep in enumerate(episodes, start=2):
    ws_out.row_dimensions[row_idx].height = 20

    c_no = ws_out.cell(row=row_idx, column=1, value=ep['no'])
    c_date = ws_out.cell(row=row_idx, column=2, value=ep['date'])
    c_year = ws_out.cell(row=row_idx, column=3, value=ep['year'])
    c_topic = ws_out.cell(row=row_idx, column=4, value=ep['topic'] or '-')
    c_guest = ws_out.cell(row=row_idx, column=5, value=ep['guest'] or '-')
    c_note = ws_out.cell(row=row_idx, column=6, value=ep['note'] or '')
    c_status = ws_out.cell(row=row_idx, column=7, value=ep['status'])

    # YT link
    c_yt = ws_out.cell(row=row_idx, column=8)
    if ep['has_yt']:
        yt_str = " ".join(ep['yt_links'])
        c_yt.value = yt_str
        c_yt.hyperlink = ep['yt_links'][0]
        c_yt.font = font_link
    else:
        c_yt.value = "-"
        c_yt.font = font_regular

    # Arch link
    c_arch = ws_out.cell(row=row_idx, column=9)
    if ep['has_arch']:
        c_arch.value = ep['arch_link']
        c_arch.hyperlink = ep['arch_link']
        c_arch.font = font_arch_link
    else:
        c_arch.value = "-"
        c_arch.font = font_regular

    # Old link
    c_old = ws_out.cell(row=row_idx, column=10)
    if ep['old_link']:
        c_old.value = ep['old_link']
        c_old.hyperlink = ep['old_link']
        c_old.font = font_link
    else:
        c_old.value = "-"
        c_old.font = font_regular

    # Stilleri belirle
    row_fill = fill_yt if ep['type'] == 'yt' else (fill_arch if ep['type'] == 'arch' else fill_missing)

    c_no.alignment = Alignment(horizontal="center", vertical="center")
    c_no.font = font_bold
    c_date.alignment = Alignment(horizontal="center", vertical="center")
    c_date.font = font_bold
    c_year.alignment = Alignment(horizontal="center", vertical="center")
    c_year.font = font_regular
    c_topic.alignment = Alignment(horizontal="left", vertical="center")
    c_topic.font = font_bold
    c_guest.alignment = Alignment(horizontal="left", vertical="center")
    c_guest.font = font_regular
    c_note.alignment = Alignment(horizontal="left", vertical="center")
    c_note.font = font_regular
    c_status.alignment = Alignment(horizontal="center", vertical="center")
    
    if ep['type'] == 'yt':
        c_status.font = font_yt_badge
    elif ep['type'] == 'arch':
        c_status.font = font_arch_badge
    else:
        c_status.font = font_missing_badge

    c_yt.alignment = Alignment(horizontal="left", vertical="center")
    c_arch.alignment = Alignment(horizontal="left", vertical="center")
    c_old.alignment = Alignment(horizontal="left", vertical="center")

    for col_idx in range(1, 11):
        cell = ws_out.cell(row=row_idx, column=col_idx)
        cell.border = thin_border
        if cell.fill.fill_type is None:
            cell.fill = row_fill

# Otomatik sütun genişlikleri
col_widths = {
    1: 10,   # Prog. No
    2: 15,   # Tarih
    3: 8,    # Yıl
    4: 35,   # Konu
    5: 25,   # Konuk
    6: 22,   # Not
    7: 18,   # Durum
    8: 45,   # YT Link
    9: 45,   # Arch Link
    10: 35   # Old Link
}
for col_idx, width in col_widths.items():
    ws_out.column_dimensions[get_column_letter(col_idx)].width = width

# AutoFilter & Freeze Panes
ws_out.auto_filter.ref = f"A1:J{len(episodes)+1}"
ws_out.freeze_panes = "A2"

excel_filename = "Tarihin_Arka_Odasi_Tam_Arsiv.xlsx"
wb_out.save(excel_filename)
wb_out.save("bölümler.xlsx")
wb_out.save("bölümler_tam_arsiv.xlsx")
print(f"✓ {excel_filename} ve bölümler.xlsx kaydedildi!")

# ==========================================================
# 4. GENERATE GITHUB README.md (.md)
# ==========================================================
print("4. GitHub README.md üretiliyor...")

md_lines = []

md_lines.append("# 🏛️ Tarihin Arka Odası — Eksiksiz Bölüm Arşivi (2008 – 2015)")
md_lines.append("")
md_lines.append("> **Kanal 1 & Habertürk** ekranlarında 2008 – 2015 yılları arasında yayınlanan efsanevi tarih programı **Tarihin Arka Odası**'nın (Murat Bardakçı, Erhan Afyoncu, Pelin Batu, Nurhan Atasoy, Selin Barlas) bilinen **354 bölümünün tamamını** içeren kapsamlı izleme kataloğu ve doğrudan oynatma arşividir.")
md_lines.append("")

# Badges
md_lines.append(f"[![Toplam Bölüm](https://img.shields.io/badge/Toplam_Bölüm-{total_count}-blue.svg)](#) ")
md_lines.append(f"[![YouTube](https://img.shields.io/badge/YouTube'da_Mevcut-{yt_count}-red.svg)](#) ")
md_lines.append(f"[![Web Arşivi](https://img.shields.io/badge/Web_Arşivi_(.webm)-{arch_count}-success.svg)](#) ")
md_lines.append(f"[![Kalan Eksik](https://img.shields.io/badge/Kalan_Eksik-{missing_count}-lightgrey.svg)](#kalan-15-eksik-bölüm) ")
md_lines.append(f"[![Erişilebilirlik Oranı](https://img.shields.io/badge/Kurtarma_Oranı-{ready_ratio}-brightgreen.svg)](#)")
md_lines.append("")

# Table of contents & shortcuts
md_lines.append("## 📌 Hızlı Gezinti & Yıllar")
md_lines.append("")
md_lines.append("- 🌐 **[Canlı İnteraktif Arama & Oynatma Paneli (index.html)](index.html)** *(GitHub Pages veya doğrudan tarayıcı ile çalışır)*")
md_lines.append("- 📊 **[Tüm Bölümler Excel Tablosu (Tarihin_Arka_Odasi_Tam_Arsiv.xlsx)](Tarihin_Arka_Odasi_Tam_Arsiv.xlsx)**")
md_lines.append("- ⚠️ **[Kalan 15 Eksik Bölüm Listesi](#kalan-15-eksik-bölüm)** *(Topluluk katkısı aranıyor)*")
md_lines.append("- 📅 **Yıllara Göre Bölümler:** ")

years_list = sorted(list(set(e['year'] for e in episodes)))
year_links = [f"[{yr}](#{yr})" for yr in years_list]
md_lines.append("  " + " • ".join(year_links))
md_lines.append("")

# Nasıl İzlenir?
md_lines.append("---")
md_lines.append("## 🎬 Nasıl İzlenir ve Oynatılır?")
md_lines.append("")
md_lines.append("1. **🔴 YouTube Bölümleri:** Tablodaki `▶ YouTube` butonuna veya linkine tıklayarak doğrudan YouTube üzerinden yüksek kalitede izleyebilirsiniz.")
md_lines.append("2. **🟢 Web Arşivi (.webm) Bölümleri:** YouTube'dan kaldırılan ancak Web Arşivi üzerinden kurtarılan 144 bölüm, doğrudan video akış bağlantısı (`.webm`) içerir:")
md_lines.append("   - **Tarayıcıda:** Linke tıkladığınızda Chrome, Firefox, Safari veya Edge doğrudan videoyu oynatır.")
md_lines.append("   - **VLC / MPV Player:** Linke sağ tıklayıp *Bağlantıyı Kopyala* deyin, VLC Player'da `Medya -> Ağ Akışı Aç` menüsüne yapıştırarak kesintisiz izleyin.")
md_lines.append("   - **İndirme:** Linke sağ tıklayıp *Farklı Kaydet* diyerek veya `aria2c` / `curl` ile bilgisayarınıza indirebilirsiniz.")
md_lines.append("")

# Eksik bölümler tablosu
md_lines.append("---")
md_lines.append("## ⚠️ Kalan 15 Eksik Bölüm")
md_lines.append("")
md_lines.append("> Bu bölümler ne YouTube'da ne de kurtarılabilen Web Arşivlerinde henüz bulunamamıştır. Elinde bu yayınların kaydı olanların lütfen katkı sunması rica olunur.")
md_lines.append("")
md_lines.append("| No | Yayın Tarihi | Konu | Konuk | Not |")
md_lines.append("| :---: | :---: | :--- | :--- | :--- |")
for ep in episodes:
    if ep['type'] == 'missing':
        md_lines.append(f"| **{ep['no']}** | {ep['date']} | {ep['topic'] or '-'} | {ep['guest'] or '-'} | {ep['note'] or '-'} |")
md_lines.append("")

# Yıl yıl bölümler tablosu
md_lines.append("---")
md_lines.append("## 📜 Tüm Bölümler Kataloğu (354 Bölüm)")
md_lines.append("")

for yr in years_list:
    yr_episodes = [e for e in episodes if e['year'] == yr]
    yr_yt = sum(1 for e in yr_episodes if e['type'] == 'yt')
    yr_arch = sum(1 for e in yr_episodes if e['type'] == 'arch')
    yr_missing = sum(1 for e in yr_episodes if e['type'] == 'missing')

    md_lines.append(f"### <a id=\"{yr}\"></a>📅 {yr} Yılı Bölümleri ({len(yr_episodes)} Bölüm)")
    md_lines.append(f"*Durum: 🔴 {yr_yt} YouTube • 🟢 {yr_arch} Web Arşivi • ⚪ {yr_missing} Eksik*")
    md_lines.append("")
    md_lines.append("| No | Tarih | Konu | Konuk | Durum | Oynat / İzle | Doğrudan Linkler |")
    md_lines.append("| :---: | :---: | :--- | :--- | :---: | :--- | :--- |")

    for ep in yr_episodes:
        # Durum rozeti
        if ep['type'] == 'yt':
            status_badge = "🔴 YouTube"
            play_btn = f"[▶ **YouTube'da İzle**]({ep['yt_links'][0]})"
            if len(ep['yt_links']) == 1:
                direct_links = f"[Link]({ep['yt_links'][0]})"
            else:
                parts = [f"[Part {i+1}]({l})" for i, l in enumerate(ep['yt_links'])]
                direct_links = " ".join(parts)
        elif ep['type'] == 'arch':
            status_badge = "🟢 Arşiv (.webm)"
            play_btn = f"[🏛️ **Arşivden Oynat**]({ep['arch_link']})"
            direct_links = f"[Doğrudan .webm]({ep['arch_link']})"
            if ep['old_link']:
                direct_links += f" • [Eski Link]({ep['old_link']})"
        else:
            status_badge = "⚪ Eksik"
            play_btn = "*Kayıt Yok*"
            direct_links = "—"

        topic_clean = (ep['topic'] or '-').replace('|', '/')
        guest_clean = (ep['guest'] or '-').replace('|', '/')
        note_suffix = f" *({ep['note']})*" if ep['note'] else ""

        md_lines.append(f"| **{ep['no']}** | {ep['date']} | {topic_clean}{note_suffix} | {guest_clean} | {status_badge} | {play_btn} | {direct_links} |")

    md_lines.append("")

# Footer
md_lines.append("---")
md_lines.append("## 🤝 Katkıda Bulunma & Teşekkür")
md_lines.append("")
md_lines.append("- İlk arşiv taramasını ve bölüm listesini hazırlayan sayın **Ümit Duran**'a ve YouTube topluluğuna teşekkür ederiz.")
md_lines.append("- Eksik 15 bölümün arşivine sahipseniz lütfen bir **Issue** veya **Pull Request** açarak projeye katkıda bulunun.")
md_lines.append("")

readme_content = "\n".join(md_lines)
with open('README.md', 'w', encoding='utf-8') as f:
    f.write(readme_content)
print("✓ README.md başarıyla üretildi!")

print("\n=== TÜM DOSYALAR HAZIR ===")
print("1. index.html (ve arsiv_paneli.html) -> Self-contained interaktif web oynatıcı")
print("2. Tarihin_Arka_Odasi_Tam_Arsiv.xlsx & bölümler.xlsx -> Profesyonel biçimlendirilmiş Excel arşivi")
print("3. README.md -> GitHub deposu için tam Markdown katalog")
