#!/usr/bin/env python3
"""Sovereign Engine - Solana Zinciri Analizi"""

import requests
from datetime import datetime, timezone

RPC = "https://api.mainnet-beta.solana.com"

def analyze_solana(address):
    print(f"\n[SOLANA] {address[:20]}...")
    flags = []
    skor = 0

    def rpc(method, params):
        r = requests.post(RPC, json={
            "jsonrpc": "2.0", "id": 1,
            "method": method, "params": params
        }, timeout=10)
        return r.json().get("result", {})

    # Bakiye
    bal = rpc("getBalance", [address])
    sol = (bal.get("value", 0) if isinstance(bal, dict) else bal or 0) / 1e9
    print(f"  Bakiye    : {sol:.6f} SOL")

    # Tx geçmişi
    sigs = rpc("getSignaturesForAddress", [address, {"limit": 50}])
    tx_count = len(sigs) if isinstance(sigs, list) else 0
    print(f"  Tx sayısı : {tx_count} (son 50)")

    if sol < 0.001 and tx_count > 0:
        flags.append("KUCUK_BAKIYE"); skor += 10
    if tx_count >= 50:
        flags.append("YUKSEK_TX"); skor += 10

    skor = min(skor, 100)
    seviye = ("KRİTİK 🔴" if skor>=70 else "YÜKSEK 🟠" if skor>=50 else "ORTA 🟡" if skor>=30 else "DÜŞÜK 🟢")
    print(f"  Risk      : {skor}/100 — {seviye}")
    if flags: print(f"  Bayraklar : {', '.join(flags)}")

    return {"adres": address, "zincir": "SOL", "bakiye_sol": round(sol,6), "tx_sayisi": tx_count, "risk_skoru": skor, "bayraklar": flags}

if __name__ == "__main__":
    analyze_solana("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")
