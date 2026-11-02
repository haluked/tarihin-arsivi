"""
Tarihin Arka Odası — İnternet Arşivi Otomasyon Tarayıcısı
API: https://findyoutubevideo.thetechrobo.ca/api/v5/:videoid

Kullanım:
  python arsiv_otomasyonu.py --test         (İlk 5 eksik bölümü test eder)
  python arsiv_otomasyonu.py --limit 20     (20 eksik bölümü tarar)
  python arsiv_otomasyonu.py --all          (Tüm eksik bölümleri sırayla tarar)
  python arsiv_otomasyonu.py --report       (Şu ana kadar bulunanları özetler)
"""

import sys
import os
import json
import time
import argparse
import urllib.request
import re

sys.stdout.reconfigure(encoding='utf-8')

CACHE_FILE = 'arsiv_tarama_sonuclari.json'
PANEL_FILE = 'arsiv_paneli.html'
API_BASE = 'https://findyoutubevideo.thetechrobo.ca/api/v5'

def load_episodes():
    if not os.path.exists(PANEL_FILE):
        print(f"HATA: {PANEL_FILE} bulunamadı.")
        return []
    with open(PANEL_FILE, 'r', encoding='utf-8') as f:
        m = re.search(r'const episodes = (\[.*?\]);', f.read(), re.DOTALL)
        if m:
            return json.loads(m.group(1))
    return []

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def query_finder_api(video_id, retries=1):
    url = f"{API_BASE}/{video_id}"
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'TarihinArsiviBot/1.0 (Research Archive Tool)'
        }
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                return data
        except urllib.error.HTTPError as e:
            return {'status': 'http_error', 'code': e.code, 'error': str(e)}
        except Exception as e:
            if attempt < retries:
                time.sleep(2)
                continue
            return {'status': 'error', 'error': str(e)}

def parse_archive_result(data):
    if not data or data.get('status') != 'ok':
        return {
            'has_video': False,
            'verdict': data.get('error', 'Hata'),
            'video_links': [],
            'meta_links': []
        }
    
    verdict = data.get('verdict', {})
    has_video = verdict.get('video', False)
    human_verdict = verdict.get('human_friendly', 'Bilinmiyor')
    
    video_links = []
    meta_links = []

    for key in data.get('keys', []):
        if not key.get('archived'):
            continue
        service_name = key.get('name', 'Bilinmeyen Servis')
        for item in key.get('available', []):
            u = item.get('url')
            if not u:
                continue
            title = item.get('title') or service_name
            contains = item.get('contains') or {}
            
            is_vid = contains.get('video') or contains.get('standalone_video')
            info = {
                'service': service_name,
                'title': title,
                'url': u,
                'is_video': is_vid
            }
            if is_vid:
                video_links.append(info)
            else:
                meta_links.append(info)

    return {
        'has_video': bool(has_video or len(video_links) > 0),
        'verdict': human_verdict,
        'video_links': video_links,
        'meta_links': meta_links
    }

def print_report(cache, episodes):
    ep_map = {e['old_video_id']: e for e in episodes if e.get('old_video_id')}
    
    print("\n" + "="*70)
    print("      TARİHİN ARKA ODASI — İNTERNET ARŞİVİ TARAMA RAPORU")
    print("="*70)
    
    total_scanned = len(cache)
    videos_found = [vid for vid, res in cache.items() if res.get('parsed', {}).get('has_video')]
    meta_only = [vid for vid, res in cache.items() if not res.get('parsed', {}).get('has_video') and (res.get('parsed', {}).get('meta_links') or 'meta' in str(res.get('parsed', {}).get('verdict', '')).lower())]
    not_found = [vid for vid, res in cache.items() if vid not in videos_found and vid not in meta_only]

    print(f"Toplam Taranan Eski Link : {total_scanned}")
    print(f"🎯 Tam Video Bulunanlar  : {len(videos_found)}")
    print(f"📑 Sadece Metadata / Altyazı: {len(meta_only)}")
    print(f"❌ Arşivde Bulunamayan   : {len(not_found)}")
    print("="*70)

    if videos_found:
        print("\n🎯 VİDEOSU BULUNAN BÖLÜMLER:")
        for vid in videos_found:
            ep = ep_map.get(vid, {})
            p_no = ep.get('id', '?')
            date_tr = ep.get('date_tr', '?')
            topic = ep.get('topic', '')
            res = cache[vid]['parsed']
            print(f"\n[{p_no}] {date_tr} - {topic} (YT: {vid})")
            print(f"   Durum: {res['verdict']}")
            for l in res['video_links']:
                print(f"   -> [{l['service']}] {l['title']}: {l['url']}")
    
    print("\n" + "="*70 + "\n")

def scan(limit=None, delay=1.5):
    episodes = load_episodes()
    cache = load_cache()

    missing_candidates = [
        e for e in episodes
        if not e.get('has_link') and e.get('old_video_id')
    ]

    to_scan = [e for e in missing_candidates if e['old_video_id'] not in cache]

    print(f"Eski linki olan toplam eksik bölüm: {len(missing_candidates)}")
    print(f"Daha önce taranmış olanlar: {len(missing_candidates) - len(to_scan)}")
    print(f"Taranacak kalan bölüm sayısı: {len(to_scan)}")

    if not to_scan:
        print("Taranacak yeni bölüm yok! Mevcut sonuçlar listeleniyor:")
        print_report(cache, episodes)
        return

    if limit:
        to_scan = to_scan[:limit]
        print(f"Bu oturumda taranacak adet: {len(to_scan)}")

    print("-" * 60)
    for idx, ep in enumerate(to_scan, 1):
        vid = ep['old_video_id']
        p_no = ep['id']
        date_tr = ep['date_tr']
        topic = ep['topic']

        print(f"[{idx}/{len(to_scan)}] No: {p_no} | {date_tr} | {topic[:30]} | ID: {vid} ...", end=" ", flush=True)

        raw_resp = query_finder_api(vid)
        parsed = parse_archive_result(raw_resp)

        cache[vid] = {
            'ep_id': p_no,
            'date_tr': date_tr,
            'topic': topic,
            'queried_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'parsed': parsed,
            'raw': raw_resp
        }
        save_cache(cache)

        if parsed['has_video']:
            print(f"🎯 VIDEO BULUNDU! ({parsed['verdict']})")
        elif parsed['meta_links']:
            print(f"📑 Metadata/Altyazı ({parsed['verdict']})")
        else:
            print(f"❌ {parsed['verdict']}")

        if idx < len(to_scan):
            time.sleep(delay)

    print("-" * 60)
    print("Tarama tamamlandı! Rapor oluşturuluyor...")
    print_report(cache, episodes)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Tarihin Arka Odası Arşiv Tarayıcı")
    parser.add_argument('--test', action='store_true', help="İlk 5 eksik bölümü test et")
    parser.add_argument('--limit', type=int, default=None, help="Belirli sayıda bölüm tara")
    parser.add_argument('--all', action='store_true', help="Tüm eksik bölümleri tara")
    parser.add_argument('--report', action='store_true', help="Kayıtlı tarama raporunu göster")
    parser.add_argument('--delay', type=float, default=1.5, help="İstekler arası bekleme süresi (sn)")

    args = parser.parse_args()

    if args.report:
        cache = load_cache()
        episodes = load_episodes()
        print_report(cache, episodes)
    elif args.test:
        scan(limit=5, delay=args.delay)
    elif args.limit:
        scan(limit=args.limit, delay=args.delay)
    elif args.all:
        scan(limit=None, delay=args.delay)
    else:
        # Default: explain options and show report
        cache = load_cache()
        episodes = load_episodes()
        if cache:
            print_report(cache, episodes)
        else:
            print("Arşiv Otomasyon Tarayıcısı hazır!")
            print("Çalıştırmak için:")
            print("  python arsiv_otomasyonu.py --test       (5 bölüm test)")
            print("  python arsiv_otomasyonu.py --limit 20   (20 bölüm)")
            print("  python arsiv_otomasyonu.py --all        (Tümünü tara)")
