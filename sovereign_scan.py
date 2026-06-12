#!/usr/bin/env python3
"""
Sovereign Engine - Ana Tarama Motoru
Toplu tarama | Telegram bildirimi | ETH + BTC
Kullanim:
  python3 sovereign_scan.py -a 0xADRES              # tek ETH
  python3 sovereign_scan.py -a BTCADRES --btc        # tek BTC
  python3 sovereign_scan.py -f adresler.txt          # toplu
  python3 sovereign_scan.py -f adresler.txt --flow   # fund flow ile
"""

import argparse, json, time, sys
from datetime import datetime, timezone
from pathlib import Path
import requests

# Blockscout modülünü import et
sys.path.insert(0, str(Path.home() / "projeler"))
from blockscout_forensics import analyze, fund_flow, fund_flow_btc, save, analyze_btc, analyze_btc_blockstream, risk_v2

OUTPUT_DIR = Path.home() / "FORENSICS"

# ─── TELEGRAM ────────────────────────────────────────────────────────────────

TG_CONFIG = {
    "token": "",   # ~/.env_keys içinden yükle
    "chat_id": "",
}

def load_env():
    env_file = Path.home() / ".env_keys"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "TG_TOKEN=" in line:
                TG_CONFIG["token"] = line.split("=",1)[1].strip()
            if "TG_CHAT_ID=" in line:
                TG_CONFIG["chat_id"] = line.split("=",1)[1].strip()

def send_telegram(alert: dict):
    if not TG_CONFIG["token"] or "YOUR" in TG_CONFIG["token"]:
        return
    skor = alert.get("risk_skoru", 0)
    seviye = alert.get("risk_seviyesi", "")
    adres = alert.get("adres", "")[:20]
    bayraklar = ", ".join(alert.get("bayraklar", [])) or "Yok"
    zincir = alert.get("zincir", "ETH")

    text = (
        f"🔍 *Sovereign Engine Alert*\n"
        f"⛓ Zincir: `{zincir}`\n"
        f"📍 Adres: `{adres}...`\n"
        f"📊 Risk: `{skor}/100` — {seviye}\n"
        f"🚩 Bayraklar: `{bayraklar}`\n"
        f"🕐 `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC`"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_CONFIG['token']}/sendMessage",
            json={"chat_id": TG_CONFIG["chat_id"], "text": text, "parse_mode": "Markdown"},
            timeout=10
        )
        print(f"  📱 Telegram bildirimi gönderildi")
    except Exception as e:
        print(f"  ⚠️ Telegram hatası: {e}")

# ─── TOPLU TARAMA ────────────────────────────────────────────────────────────

def scan_file(filepath: str, flow: bool = False, risk_threshold: int = 0):
    path = Path(filepath)
    if not path.exists():
        print(f"❌ Dosya bulunamadı: {filepath}")
        sys.exit(1)

    adresler = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            adresler.append(line)

    print(f"📋 {len(adresler)} adres yüklendu: {filepath}")
    print(f"⚡ Eşik: risk_skoru >= {risk_threshold}")
    print("=" * 50)

    sonuclar = []
    for i, adres in enumerate(adresler, 1):
        print(f"\n[{i}/{len(adresler)}]", end="")

        # BTC mi ETH mi?
        if adres.startswith("1") or adres.startswith("3") or adres.startswith("bc1"):
            result = analyze_btc_blockstream(adres)
        else:
            result = analyze(adres)

        if "error" not in result:
            sonuclar.append(result)

            # Eşik aşıldıysa Telegram
            if result.get("risk_skoru", 0) >= risk_threshold and risk_threshold > 0:
                send_telegram(result)

            # Fund flow
            if flow and result.get("risk_skoru", 0) >= 30:
                result["fund_flow"] = fund_flow(adres, 1)

        # API rate limit
        time.sleep(1)

    # Özet rapor
    ozet = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "toplam": len(adresler),
        "basarili": len(sonuclar),
        "yuksek_risk": [r for r in sonuclar if r.get("risk_skoru",0) >= 50],
        "orta_risk": [r for r in sonuclar if 30 <= r.get("risk_skoru",0) < 50],
        "dusuk_risk": [r for r in sonuclar if r.get("risk_skoru",0) < 30],
        "sonuclar": sonuclar,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    f = OUTPUT_DIR / f"toplu_tarama_{ts}.json"
    with open(f, "w") as fp:
        json.dump(ozet, fp, indent=2, default=str)

    print(f"\n{'='*50}")
    print(f"  TARAMA TAMAMLANDI")
    print(f"  Toplam     : {ozet['toplam']}")
    print(f"  Yüksek risk: {len(ozet['yuksek_risk'])} adres 🔴")
    print(f"  Orta risk  : {len(ozet['orta_risk'])} adres 🟡")
    print(f"  Düşük risk : {len(ozet['dusuk_risk'])} adres 🟢")
    print(f"  Rapor      : {f}")

    return ozet

# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    load_env()

    ap = argparse.ArgumentParser(description="Sovereign Engine - Ana Tarama Motoru")
    ap.add_argument("-a", "--address", help="Tek adres")
    ap.add_argument("-f", "--file", help="Adres listesi dosyası")
    ap.add_argument("--btc", action="store_true", help="Bitcoin adresi")
    ap.add_argument("--flow", action="store_true", help="Fund flow ekle")
    ap.add_argument("--depth", type=int, default=1)
    ap.add_argument("--threshold", type=int, default=0,
                    help="Telegram bildirimi için minimum risk skoru")
    args = ap.parse_args()

    if not args.address and not args.file:
        ap.print_help()
        sys.exit(1)

    print("=" * 50)
    print("  Sovereign Engine — Ana Tarama Motoru")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 50)

    if args.file:
        scan_file(args.file, args.flow, args.threshold)

    elif args.address:
        if args.btc:
            result = analyze_btc_blockstream(args.address)
        else:
            result = analyze(args.address)

        if args.flow:
            if args.btc:
                result["fund_flow"] = fund_flow_btc(args.address, args.depth)
            else:
                result["fund_flow"] = fund_flow(args.address, args.depth)

        save(args.address, result)

        if result.get("risk_skoru", 0) >= 30:
            send_telegram(result)

if __name__ == "__main__":
    main()
