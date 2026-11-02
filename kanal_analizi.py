import subprocess
import json
import re
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

FFMPEG = r"C:\Program Files\Kdenlive\bin\ffmpeg.exe"

episodes = [
    r"arsivden indirilenler\[No 161] 28 Ocak 2012 - Ermeni Tehciri.webm",
    r"arsivden indirilenler\[No 104] 29 Mayıs 2010 - Istanbulun fethi.webm",
    r"arsivden indirilenler\[No 142] 20 Şubat 2011 - Sultan Abdulhamid.webm"
]

for ep in episodes:
    print("=" * 60)
    print("ANALİZ EDİLEN DOSYA:", os.path.basename(ep))
    cmd = [
        FFMPEG, "-ss", "00:20:00", "-t", "30", "-i", ep,
        "-af", "astats=metadata=1:reset=1",
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    out = res.stderr
    
    # Kanal bazlı RMS ve Peak değerlerini çekelim
    # astats format: Channel: 1 (Sol), Channel: 2 (Sağ)
    ch1_match = re.search(r"Channel: 1.*?Peak level dB:\s+([-\d.]+).*?RMS level dB:\s+([-\d.]+)", out, re.DOTALL)
    ch2_match = re.search(r"Channel: 2.*?Peak level dB:\s+([-\d.]+).*?RMS level dB:\s+([-\d.]+)", out, re.DOTALL)
    
    if ch1_match and ch2_match:
        print(f"  [SOL KANAL - Ch 1] Peak: {ch1_match.group(1)} dB | RMS (Ortalama): {ch1_match.group(2)} dB")
        print(f"  [SAĞ KANAL - Ch 2] Peak: {ch2_match.group(1)} dB | RMS (Ortalama): {ch2_match.group(2)} dB")
        diff = abs(float(ch1_match.group(2)) - float(ch2_match.group(2)))
        print(f"  --> Kanallar Arası Fark: {diff:.1f} dB")
        if float(ch2_match.group(2)) < -60 or diff > 15:
            print("  🚨 TESPİT: SAĞ KANAL NEREDEYSE TAMAMEN SESSİZ / BOŞ! (Tek taraflı ses hatası)")
        else:
            print("  --> İki kanalda da ses mevcut.")
    else:
        print("  astats ayrıştırılamadı, ham çıktıdan arama yapılıyor:")
        for line in out.splitlines():
            if "RMS level dB:" in line or "Peak level dB:" in line:
                print("   ", line.strip())
