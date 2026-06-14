#!/usr/bin/env python3
"""Sovereign Engine - Zaman Serisi Analizi"""
import requests, time
from datetime import datetime, timezone
from collections import defaultdict

def btc_time_series(address, max_sayfa=5):
    print(f"\n[ZAMAN SERİSİ] {address[:20]}...")
    txs = []
    last_txid = None

    for sayfa in range(max_sayfa):
        url = f"https://blockstream.info/api/address/{address}/txs"
        if last_txid:
            url += f"/chain/{last_txid}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200: break
        batch = r.json()
        if not batch: break
        txs.extend(batch)
        last_txid = batch[-1]["txid"]
        time.sleep(0.5)

    # Aylık aktivite
    aylik = defaultdict(int)
    for t in txs:
        bt = t.get("status", {}).get("block_time", 0)
        if bt:
            ay = datetime.fromtimestamp(bt, timezone.utc).strftime("%Y-%m")
            aylik[ay] += 1

    print(f"  Toplam tx : {len(txs)}")
    print(f"\n  Aylık Aktivite:")
    for ay in sorted(aylik.keys()):
        bar = "█" * min(aylik[ay], 40)
        print(f"  {ay}: {bar} ({aylik[ay]})")

    return dict(aylik)

if __name__ == "__main__":
    btc_time_series("34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo", max_sayfa=3)
