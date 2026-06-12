#!/usr/bin/env python3
"""
Sovereign Engine - Master Report Generator v1.0
Tüm analiz sonuçlarını birleştirip JSON + Markdown rapor üretir
"""

import json
import glob
from datetime import datetime, timezone
from pathlib import Path

FORENSICS_DIR = Path.home() / "FORENSICS"
REPORTS_DIR = Path.home() / "FORENSICS" / "master_raporlar"

def load_all_reports():
    """FORENSICS klasöründeki tüm JSON raporları yükle"""
    raporlar = []
    for f in sorted(glob.glob(str(FORENSICS_DIR / "*.json"))):
        try:
            with open(f) as fp:
                data = json.load(fp)
                data["_dosya"] = Path(f).name
                raporlar.append(data)
        except:
            pass
    return raporlar

def ozetle(raporlar):
    """Tüm raporlardan özet istatistik çıkar"""
    toplam = len(raporlar)
    yuksek = []
    orta = []
    dusuk = []
    tum_bayraklar = {}

    for r in raporlar:
        # Tek adres raporu
        risk = r.get("risk_analizi", r.get("risk", {}))
        skor = risk.get("risk_skoru", 0) if risk else 0
        adres = r.get("adres", r.get("target", "?"))

        entry = {
            "adres": adres,
            "skor": skor,
            "seviye": risk.get("risk_seviyesi", "?") if risk else "?",
            "bayraklar": risk.get("bayraklar", []) if risk else [],
            "dosya": r.get("_dosya", ""),
        }

        for b in entry["bayraklar"]:
            tum_bayraklar[b] = tum_bayraklar.get(b, 0) + 1

        if skor >= 50:
            yuksek.append(entry)
        elif skor >= 30:
            orta.append(entry)
        else:
            dusuk.append(entry)

        # Toplu tarama raporu
        if "sonuclar" in r:
            for s in r["sonuclar"]:
                s_skor = s.get("risk_skoru", 0)
                s_entry = {
                    "adres": s.get("adres", "?"),
                    "skor": s_skor,
                    "seviye": s.get("risk_seviyesi", "?"),
                    "bayraklar": s.get("bayraklar", []),
                    "dosya": r.get("_dosya", ""),
                }
                for b in s_entry["bayraklar"]:
                    tum_bayraklar[b] = tum_bayraklar.get(b, 0) + 1
                if s_skor >= 50:
                    yuksek.append(s_entry)
                elif s_skor >= 30:
                    orta.append(s_entry)

    return {
        "toplam_rapor": toplam,
        "yuksek_risk": yuksek,
        "orta_risk": orta,
        "dusuk_risk": dusuk,
        "bayrak_frekansi": dict(sorted(tum_bayraklar.items(), key=lambda x: -x[1])),
    }

def markdown_yaz(ozet, cikti_dosya):
    """Markdown formatında rapor yaz"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    md = f"""# 🔍 Sovereign Engine — Master Forensics Raporu

**Tarih:** {ts} UTC  
**Analist:** Sovereign Engine v1.0  
**Veri Kaynağı:** Blockstream.info, Blockscout ETH API  

---

## 📊 Yönetici Özeti

| Kategori | Sayı |
|----------|------|
| Toplam Rapor | {ozet['toplam_rapor']} |
| Yüksek Risk 🔴 | {len(ozet['yuksek_risk'])} |
| Orta Risk 🟡 | {len(ozet['orta_risk'])} |
| Düşük Risk 🟢 | {len(ozet['dusuk_risk'])} |

---

## 🚨 Yüksek Risk Adresleri

"""
    if ozet["yuksek_risk"]:
        for a in ozet["yuksek_risk"]:
            md += f"### `{a['adres']}`\n"
            md += f"- **Risk Skoru:** {a['skor']}/100 — {a['seviye']}\n"
            md += f"- **Bayraklar:** {', '.join(a['bayraklar']) or 'Yok'}\n"
            md += f"- **Kaynak:** {a['dosya']}\n\n"
    else:
        md += "_Yüksek riskli adres tespit edilmedi._\n\n"

    md += "## ⚠️ Orta Risk Adresleri\n\n"
    if ozet["orta_risk"]:
        for a in ozet["orta_risk"]:
            md += f"- `{a['adres']}` — Skor: {a['skor']} | {', '.join(a['bayraklar'])}\n"
    else:
        md += "_Orta riskli adres tespit edilmedi._\n\n"

    md += "\n## 🚩 En Sık Görülen Bayraklar\n\n"
    for bayrak, sayi in list(ozet["bayrak_frekansi"].items())[:10]:
        md += f"- `{bayrak}`: {sayi} adres\n"

    md += f"""
---

## 📋 Metodoloji Notu

Bu rapor Sovereign Engine v1.0 tarafından otomatik üretilmiştir.
- Veriler kamuya açık blockchain API'lerinden alınmıştır
- Risk skorları heuristik kurallara dayanmaktadır
- Bulgular doğrulama gerektirmektedir

**Sorumluluk Reddi:** Bu rapor yalnızca araştırma ve eğitim amaçlıdır.
"""
    with open(cikti_dosya, "w") as f:
        f.write(md)
    print(f"📄 Markdown rapor: {cikti_dosya}")

def main():
    print("=" * 55)
    print("  Sovereign Engine — Master Report Generator")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 55)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    print("\n📂 Raporlar yükleniyor...")
    raporlar = load_all_reports()
    print(f"  {len(raporlar)} rapor bulundu")

    print("\n📊 Analiz ediliyor...")
    ozet = ozetle(raporlar)

    # JSON kaydet
    json_dosya = REPORTS_DIR / f"master_{ts}.json"
    with open(json_dosya, "w") as f:
        json.dump(ozet, f, indent=2, default=str)
    print(f"💾 JSON rapor: {json_dosya}")

    # Markdown kaydet
    md_dosya = REPORTS_DIR / f"master_{ts}.md"
    markdown_yaz(ozet, md_dosya)

    # Terminal özeti
    print(f"\n{'='*55}")
    print(f"  ÖZET")
    print(f"{'='*55}")
    print(f"  Toplam rapor : {ozet['toplam_rapor']}")
    print(f"  Yüksek risk  : {len(ozet['yuksek_risk'])} adres 🔴")
    print(f"  Orta risk    : {len(ozet['orta_risk'])} adres 🟡")
    print(f"  Düşük risk   : {len(ozet['dusuk_risk'])} adres 🟢")
    if ozet["bayrak_frekansi"]:
        print(f"  En sık bayrak: {list(ozet['bayrak_frekansi'].keys())[0]}")

if __name__ == "__main__":
    main()
