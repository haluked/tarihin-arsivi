import urllib.request
import json
import re
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirect)

with open('arsiv_paneli.html', 'r', encoding='utf-8') as f:
    m = re.search(r'const episodes = (\[.*?\]);', f.read(), re.DOTALL)
episodes = json.loads(m.group(1))

missing_vids = [e for e in episodes if not e.get('has_link') and e.get('old_video_id')]
print(f"Toplam taranacak eksik bölüm: {len(missing_vids)}")

results = []

for idx, ep in enumerate(missing_vids, 1):
    vid = ep['old_video_id']
    p_no = ep['id']
    date_tr = ep['date_tr']
    topic = ep['topic']
    
    url = f"https://tube.archivarix.net/api/videos/{vid}/file"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    
    status = None
    direct_url = None
    
    try:
        resp = opener.open(req)
        status = 200
        direct_url = url
    except urllib.error.HTTPError as e:
        status = e.code
        if e.code == 302:
            direct_url = e.headers.get('Location')
    except Exception as e:
        status = f"Err: {e}"

    if status == 302 and direct_url:
        print(f"[{idx}/{len(missing_vids)}] 🎯 BULUNDU: [{p_no}] {date_tr} - {topic[:25]} -> {direct_url}")
        results.append({
            'id': p_no,
            'date_tr': date_tr,
            'topic': topic,
            'guest': ep.get('guest'),
            'old_video_id': vid,
            'found': True,
            'download_url': direct_url
        })
    else:
        print(f"[{idx}/{len(missing_vids)}] ❌ Bulunamadı ({status}): [{p_no}] {date_tr}")
        results.append({
            'id': p_no,
            'date_tr': date_tr,
            'topic': topic,
            'guest': ep.get('guest'),
            'old_video_id': vid,
            'found': False,
            'download_url': None
        })

    # polite delay
    time.sleep(0.4)

with open('tam_arsiv_tarama_sonuclari.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

found_list = [r for r in results if r['found']]
print("\n" + "="*70)
print(f"TARAMA TAMAMLANDI!")
print(f"Toplam Taranan: {len(results)}")
print(f"🎯 Arşivde İndirilebilir Tam Video Bulunan: {len(found_list)}")
print(f"❌ Bulunamayan: {len(results) - len(found_list)}")
print("="*70)
