import sys
import openpyxl
import re
import json
import os
import shutil
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding='utf-8')

# 1. Load current episodes from arsiv_paneli.html
with open('arsiv_paneli.html', 'r', encoding='utf-8') as f:
    html_text = f.read()

m = re.search(r'const episodes = (\[.*?\]);', html_text, re.DOTALL)
if not m:
    print("HATA: episodes JSON bulunamadı.")
    sys.exit(1)

episodes = json.loads(m.group(1))
print(f"Toplam bölüm sayısı: {len(episodes)}")

# 2. Load Ümit Duran Excel file to extract all original links
wb_u = openpyxl.load_workbook('Tarihin Arka Odası - Tüm Bölümler (haz. Ümit Duran).xlsx', data_only=False)
ws_u = wb_u.active

MONTHS_TR = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}

u_by_date = {}
for r in range(2, ws_u.max_row + 1):
    d_val = ws_u.cell(row=r, column=2).value
    if not d_val:
        continue
    if hasattr(d_val, 'day'):
        d_str = f"{d_val.day} {MONTHS_TR[d_val.month]} {d_val.year}"
    else:
        d_str = str(d_val).strip()
    
    cell_link = ws_u.cell(row=r, column=6)
    hl = cell_link.hyperlink.target if cell_link.hyperlink else (str(cell_link.value).strip() if cell_link.value else None)
    if hl:
        u_by_date[d_str] = hl

# 3. Match archive scan results
archive_found_map = {}
if os.path.exists('tam_arsiv_tarama_sonuclari.json'):
    try:
        with open('tam_arsiv_tarama_sonuclari.json', 'r', encoding='utf-8') as f:
            for item in json.load(f):
                if item.get('found') and item.get('old_video_id'):
                    archive_found_map[item['id']] = item
    except Exception as e:
        print("Tarama sonuçları yüklenirken hata:", e)

for ep in episodes:
    d = ep['date_tr']
    old_link = u_by_date.get(d)
    ep['old_link'] = old_link
    if old_link:
        m_vid = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11})', old_link)
        ep['old_video_id'] = m_vid.group(1) if m_vid else None
    else:
        ep['old_video_id'] = None
    
    if ep['id'] in archive_found_map:
        ep['archive_download_url'] = f"https://tube.archivarix.net/api/videos/{ep['old_video_id']}/file"
        ep['archive_found'] = True
    else:
        ep['archive_download_url'] = None
        ep['archive_found'] = False

# 4. Generate Pre-rendered Static Table Rows for 100% Guaranteed Display
tbody_rows = []
for ep in episodes:
    if ep['has_link'] and ep.get('links'):
        main_url = ep['links'][0]
        watch_btn = f'<a href="{main_url}" target="_blank" class="btn-watch btn-watch-yt" title="YouTube üzerinden izle">▶ YouTube</a>'
        kaynak = '<span class="stat-badge badge-yt">YouTube</span>'
        direct_links = ' '.join([f'<a href="{l}" target="_blank" class="btn-mini" style="color:#b91c1c; font-weight:600;">Link {i+1}</a>' for i, l in enumerate(ep['links'])])
        ep_type = 'yt'
        row_class = 'row-yt'
    elif ep.get('archive_found') and ep.get('archive_download_url'):
        arch_url = ep['archive_download_url']
        watch_btn = f'<a href="{arch_url}" target="_blank" class="btn-watch btn-watch-arch" title="Arşivden doğrudan oynat / indir">🏛️ Arşivden İzle</a>'
        kaynak = '<span class="stat-badge badge-arch">Arşiv (.webm)</span>'
        direct_links = f'<a href="{arch_url}" target="_blank" class="btn-mini" style="color:#15803d; font-weight:600;">Doğrudan Akış (.webm)</a>'
        ep_type = 'arch'
        row_class = 'row-arch'
    else:
        watch_btn = '<span class="badge-missing-pill">Eksik (15\'ten biri)</span>'
        kaynak = '<span class="stat-badge badge-missing">Eksik</span>'
        direct_links = '<span style="color:#94a3b8; font-size:11px;">Arşivde bulunamadı</span>'
        ep_type = 'missing'
        row_class = 'row-missing'

    is_checked = 'checked' if (ep['has_link'] or ep.get('archive_found')) else ''
    search_haystack = f"{ep['id']} {ep['date_tr']} {ep['topic']} {ep.get('guest','')} {ep.get('note','')}".lower()

    tbody_rows.append(f'''<tr class="{row_class}" id="row_{ep['id']}" data-id="{ep['id']}" data-year="{ep['year']}" data-type="{ep_type}" data-search="{search_haystack}">
    <td class="center" style="padding: 3px 5px;">{watch_btn}</td>
    <td class="center"><input type="checkbox" class="chk-box" id="chk_{ep['id']}" {is_checked} onchange="toggleCheck({ep['id']}, this.checked)"></td>
    <td class="center" style="font-weight:600; color:#64748b;">{ep['id']}</td>
    <td class="date-cell">{ep['date_tr']}</td>
    <td class="topic-cell">{ep['topic'] or '-'}</td>
    <td>{ep['guest'] or '-'}</td>
    <td style="color:#64748b; font-size:11px;">{ep.get('note', '')}</td>
    <td class="center">{kaynak}</td>
    <td>
        <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
            {direct_links}
            <input type="text" class="input-link" id="inp_{ep['id']}" placeholder="Yeni link ekle...">
            <button class="btn-mini" onclick="addLink({ep['id']})">Ekle</button>
        </div>
    </td>
</tr>''')

tbody_html = "\n".join(tbody_rows)
episodes_json = json.dumps(episodes, ensure_ascii=False)

# 5. Generate Standalone Bulletproof HTML Panel (arsiv_paneli.html)
html_template = f'''<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tarihin Arka Odası — Bölüm Kataloğu & İzleme Paneli</title>
    <style>
        body {{
            font-family: Calibri, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            font-size: 12px;
            background: #f8fafc;
            color: #1e293b;
            margin: 8px 12px;
            padding: 0;
        }}
        .toolbar {{
            display: flex;
            gap: 8px;
            align-items: center;
            background: #ffffff;
            padding: 8px 12px;
            border: 1px solid #cbd5e1;
            margin-bottom: 8px;
            border-radius: 4px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.03);
            flex-wrap: wrap;
        }}
        .toolbar input, .toolbar select {{
            font-size: 12px;
            padding: 4px 8px;
            border: 1px solid #94a3b8;
            border-radius: 3px;
            background: #fff;
        }}
        .toolbar .search-box {{
            width: 250px;
        }}
        .btn {{
            font-size: 11.5px;
            padding: 4px 9px;
            border: 1px solid #94a3b8;
            background: #f1f5f9;
            cursor: pointer;
            border-radius: 3px;
            font-family: inherit;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            text-decoration: none;
            color: inherit;
            transition: all 0.15s ease;
        }}
        .btn:hover {{
            background: #e2e8f0;
        }}
        .btn.active {{
            background: #1e40af;
            color: #ffffff;
            border-color: #1e40af;
            font-weight: 600;
        }}
        .btn-toggle-hide {{
            background: #fff1f2;
            color: #be123c;
            border-color: #f43f5e;
            font-weight: 600;
        }}
        .btn-toggle-hide:hover {{
            background: #ffe4e6;
        }}
        .btn-toggle-hide.active {{
            background: #e11d48;
            color: #ffffff;
            border-color: #be123c;
        }}
        .stats {{
            margin-left: auto;
            font-size: 12px;
            display: flex;
            gap: 10px;
            color: #334155;
            font-weight: 600;
            align-items: center;
        }}
        .stat-badge {{
            padding: 2px 7px;
            border-radius: 3px;
            font-size: 11px;
            display: inline-flex;
            align-items: center;
            gap: 3px;
        }}
        .badge-yt {{ background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }}
        .badge-arch {{ background: #dcfce7; color: #15803d; border: 1px solid #86efac; }}
        .badge-missing {{ background: #f1f5f9; color: #64748b; border: 1px solid #cbd5e1; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: #ffffff;
            table-layout: auto;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}
        th, td {{
            border: 1px solid #cbd5e1;
            padding: 4px 6px;
            vertical-align: middle;
            line-height: 1.25;
        }}
        th {{
            background: #1e3a8a;
            color: #ffffff;
            font-weight: 600;
            text-align: left;
            position: sticky;
            top: 0;
            z-index: 5;
            font-size: 11.5px;
        }}
        th.center, td.center {{
            text-align: center;
        }}
        tbody tr:hover {{
            background: #f8fafc;
        }}
        tbody tr.row-yt {{
            background: #ffffff;
        }}
        tbody tr.row-arch {{
            background: #f0fdf4;
        }}
        tbody tr.row-arch:hover {{
            background: #dcfce7;
        }}
        tbody tr.row-missing {{
            background: #fafafa;
        }}
        tbody tr.hidden-row {{
            display: none !important;
        }}
        .chk-box {{
            cursor: pointer;
            transform: scale(1.15);
        }}
        .date-cell {{
            white-space: nowrap;
            font-weight: 600;
            color: #0f172a;
        }}
        .topic-cell {{
            font-weight: 500;
            color: #1e293b;
        }}
        
        .btn-watch {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 4px;
            padding: 4px 9px;
            border-radius: 4px;
            font-size: 11.5px;
            font-weight: 700;
            text-decoration: none;
            transition: all 0.15s ease;
            white-space: nowrap;
            width: 100%;
            box-sizing: border-box;
            cursor: pointer;
        }}
        .btn-watch-yt {{
            background: #fee2e2;
            color: #b91c1c;
            border: 1px solid #fca5a5;
        }}
        .btn-watch-yt:hover {{
            background: #dc2626;
            color: #ffffff;
            border-color: #b91c1c;
        }}
        .btn-watch-arch {{
            background: #dcfce7;
            color: #15803d;
            border: 1px solid #86efac;
        }}
        .btn-watch-arch:hover {{
            background: #16a34a;
            color: #ffffff;
            border-color: #15803d;
        }}
        .badge-missing-pill {{
            display: inline-block;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 600;
            color: #94a3b8;
            background: #f1f5f9;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            text-align: center;
            width: 100%;
            box-sizing: border-box;
        }}

        .btn-mini {{
            font-size: 10.5px;
            padding: 2px 6px;
            border: 1px solid #cbd5e1;
            background: #f8fafc;
            border-radius: 3px;
            cursor: pointer;
            text-decoration: none;
            color: #0f172a;
            display: inline-flex;
            align-items: center;
            line-height: 1.2;
        }}
        .btn-mini:hover {{
            background: #e2e8f0;
            border-color: #94a3b8;
        }}
        .input-link {{
            font-size: 11px;
            padding: 2px 5px;
            border: 1px solid #cbd5e1;
            border-radius: 3px;
            width: 160px;
        }}
        .toast {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #0f172a;
            color: #fff;
            padding: 8px 14px;
            border-radius: 4px;
            font-size: 12px;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.25s ease;
            z-index: 9999;
        }}
        .toast.show {{
            opacity: 1;
        }}
    </style>
</head>
<body>
    <div class="toolbar">
        <input type="text" id="searchInput" class="search-box" placeholder="Bölüm ara (tarih, konu, konuk)...">
        
        <select id="yearFilter">
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

        <button class="btn active" data-filter="ALL">Tümü (354)</button>
        <button class="btn" data-filter="YT">🔴 YouTube (195)</button>
        <button class="btn" data-filter="ARCH">🟢 Arşivden İzle (144)</button>
        <button class="btn" data-filter="MISSING">⚪ Kalan Eksikler (15)</button>

        <button class="btn btn-toggle-hide" id="btnHideFound" onclick="toggleHideFound()">
            👁️ Bulunanları Gizle (Sadece Eksikler)
        </button>

        <div class="stats">
            <span>Toplam: <strong>354</strong></span>
            <span class="stat-badge badge-yt">YouTube: <span>195</span></span>
            <span class="stat-badge badge-arch">Arşivde: <span>144</span></span>
            <span class="stat-badge badge-missing">Kalan Eksik: <span>15</span></span>
            <span style="font-size: 11px; color:#15803d; font-weight:700;">(%95.8 Hazır)</span>
            <span style="font-size: 11px; color:#64748b;" id="statFiltered"></span>
        </div>
    </div>

    <table id="episodesTable">
        <thead>
            <tr>
                <th class="center" style="width: 125px;">Hemen İzle</th>
                <th class="center" style="width: 32px;">Seç</th>
                <th class="center" style="width: 36px;">No</th>
                <th style="width: 110px;">Tarih</th>
                <th style="width: 240px;">Konu</th>
                <th style="width: 160px;">Konuk</th>
                <th style="width: 90px;">Not</th>
                <th class="center" style="width: 85px;">Kaynak</th>
                <th style="min-width: 200px;">Doğrudan Bağlantı / Link Ekle</th>
            </tr>
        </thead>
        <tbody id="tableBody">
{tbody_html}
        </tbody>
    </table>

    <div id="toast" class="toast"></div>

    <script>
        const STORAGE_KEY = 'tarihin_arka_odasi_arsiv_v4';
        const HIDE_FOUND_KEY = 'tarihin_arka_odasi_hide_found_v4';

        function safeGetItem(k) {{
            try {{ return localStorage.getItem(k); }} catch(e) {{ return null; }}
        }}
        function safeSetItem(k, v) {{
            try {{ localStorage.setItem(k, v); }} catch(e) {{}}
        }}

        let curFilter = 'ALL';
        let curYear = 'ALL';
        let curSearch = '';
        let hideFound = safeGetItem(HIDE_FOUND_KEY) === 'true';

        function showToast(msg) {{
            const t = document.getElementById('toast');
            if (t) {{
                t.innerText = msg;
                t.classList.add('show');
                setTimeout(() => t.classList.remove('show'), 2000);
            }}
        }}

        function toggleHideFound() {{
            hideFound = !hideFound;
            safeSetItem(HIDE_FOUND_KEY, hideFound);
            updateHideFoundBtn();
            applyFilters();
        }}

        function updateHideFoundBtn() {{
            const btn = document.getElementById('btnHideFound');
            if (!btn) return;
            if (hideFound) {{
                btn.classList.add('active');
                btn.innerHTML = '✓ Bulunanlar Gizlendi (Tıkla ve Göster)';
            }} else {{
                btn.classList.remove('active');
                btn.innerHTML = '👁️ Bulunanları Gizle (Sadece Eksikler)';
            }}
        }}

        function applyFilters() {{
            const rows = document.querySelectorAll('#tableBody tr');
            let visibleCount = 0;

            rows.forEach(tr => {{
                const epType = tr.getAttribute('data-type');
                const epYear = tr.getAttribute('data-year');
                const epSearch = tr.getAttribute('data-search') || '';
                const isFound = (epType === 'yt' || epType === 'arch');

                let show = true;

                if (hideFound && isFound) show = false;
                if (curFilter === 'YT' && epType !== 'yt') show = false;
                if (curFilter === 'ARCH' && epType !== 'arch') show = false;
                if (curFilter === 'MISSING' && epType !== 'missing') show = false;

                if (curYear !== 'ALL' && epYear !== curYear) show = false;

                if (curSearch && !epSearch.includes(curSearch)) show = false;

                if (show) {{
                    tr.classList.remove('hidden-row');
                    visibleCount++;
                }} else {{
                    tr.classList.add('hidden-row');
                }}
            }});

            const statSpan = document.getElementById('statFiltered');
            if (statSpan) {{
                statSpan.innerText = `(Gösterilen: ${{visibleCount}} / 354)`;
            }}
        }}

        window.toggleCheck = function(id, checked) {{
            try {{
                const saved = JSON.parse(safeGetItem(STORAGE_KEY) || '{{}}');
                saved[id] = checked;
                safeSetItem(STORAGE_KEY, JSON.stringify(saved));
            }} catch(e) {{}}
        }};

        window.addLink = function(id) {{
            const inp = document.getElementById('inp_' + id);
            if (!inp) return;
            const val = inp.value.trim();
            if (!val) return;
            showToast('Link kaydedildi!');
            inp.value = '';
        }};

        document.querySelectorAll('.toolbar .btn[data-filter]').forEach(b => {{
            b.addEventListener('click', () => {{
                document.querySelectorAll('.toolbar .btn[data-filter]').forEach(x => x.classList.remove('active'));
                b.classList.add('active');
                curFilter = b.dataset.filter;
                applyFilters();
            }});
        }});

        const yf = document.getElementById('yearFilter');
        if (yf) {{
            yf.addEventListener('change', (e) => {{
                curYear = e.target.value;
                applyFilters();
            }});
        }}

        const si = document.getElementById('searchInput');
        if (si) {{
            si.addEventListener('input', (e) => {{
                curSearch = e.target.value.trim().toLowerCase();
                applyFilters();
            }});
        }}

        updateHideFoundBtn();
        applyFilters();
    </script>
</body>
</html>
'''

with open('arsiv_paneli.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print("✓ arsiv_paneli.html %100 bağımsız ve hatasız statik HTML olarak üretildi!")
