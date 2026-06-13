#!/usr/bin/env python3
"""Sovereign Engine - Tron Zinciri Analizi (TronGrid API)"""

import requests
from datetime import datetime, timezone
from pathlib import Path

TRONGRID_KEY = ""  # trongrid.io ücretsiz key

def analyze_tron(address):
    print(f"\n[TRON] {address[:20]}...")
    
    headers = {"TRON-PRO-API-KEY": TRONGRID_KEY} if TRONGRID_KEY else {}
    
    try:
        r = requests.get(
            f"https://apilist.tronscanapi.com/api/accountv2",
            params={"address": address},
            timeout=10
        )
        d = r.json()
    except Exception as e:
        return {"error": str(e)}

    trx = d.get("balance", 0) / 1e6
    tx_count = d.get("totalTransactionCount", 0)
    
    print(f"  Bakiye    : {trx:.6f} TRX")
    print(f"  Tx sayısı : {tx_count}")
    
    flags = []
    skor = 0
    if trx < 0.001 and tx_count > 0:
        flags.append("KUCUK_BAKIYE"); skor += 10
    if tx_count > 1000:
        flags.append("YUKSEK_TX"); skor += 10
    
    skor = min(skor, 100)
    seviye = ("KRİTİK 🔴" if skor>=70 else "YÜKSEK 🟠" if skor>=50 else "ORTA 🟡" if skor>=30 else "DÜŞÜK 🟢")
    print(f"  Risk      : {skor}/100 — {seviye}")
    
    return {"adres": address, "zincir": "TRX", "bakiye_trx": round(trx,6), "tx_sayisi": tx_count, "risk_skoru": skor, "bayraklar": flags}

if __name__ == "__main__":
    # Test adresi — kamuya açık Tron adresi
    analyze_tron("TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9")
