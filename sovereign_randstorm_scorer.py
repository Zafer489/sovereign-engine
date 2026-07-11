#!/usr/bin/env python3
"""
sovereign_randstorm_scorer.py — Randstorm RNG Zafiyeti Tespiti
2011-2015 arası BitcoinJS tabanlı cüzdanlarda zayıf tarayıcı RNG riski.
Referans: Unciphered "Randstorm" araştırması (2023).
"""

import requests
from datetime import datetime, timezone

RANDSTORM_START = datetime(2011, 1, 1, tzinfo=timezone.utc)
RANDSTORM_END = datetime(2015, 12, 31, tzinfo=timezone.utc)
GUVENLI_TX_LIMITI = 5000  # bunun üstünde tam sayfalama pratik değil


def _ilk_islem_tarihini_bul(address: str):
    """
    Döner: (tarih, toplam_tx_sayisi)
    Toplam işlem sayısı guvenli limiti asarsa tarih None doner (tahmin etmek yerine).
    """
    base = f"https://blockstream.info/api/address/{address}"

    try:
        stats = requests.get(base, timeout=10).json()
        tx_count = (
            stats.get("chain_stats", {}).get("tx_count", 0)
            + stats.get("mempool_stats", {}).get("tx_count", 0)
        )
    except Exception:
        return None, None

    if tx_count > GUVENLI_TX_LIMITI:
        return None, tx_count

    last_txid = None
    son_sayfa = None
    max_sayfa = (tx_count // 25) + 2

    for _ in range(max_sayfa):
        url = f"{base}/txs/chain" if last_txid is None else f"{base}/txs/chain/{last_txid}"
        try:
            txs = requests.get(url, timeout=10).json()
        except Exception:
            break
        if not txs:
            break
        son_sayfa = txs
        if len(txs) < 25:
            break
        last_txid = txs[-1]["txid"]

    if not son_sayfa:
        return None, tx_count

    confirmed = [t for t in son_sayfa if t.get("status", {}).get("confirmed")]
    if not confirmed:
        return None, tx_count

    oldest = min(t["status"]["block_time"] for t in confirmed)
    return datetime.fromtimestamp(oldest, tz=timezone.utc), tx_count


def randstorm_riski(address: str, chain: str = "BTC") -> dict:
    """Stage 1 çıktısına 'randstorm' anahtarı altında eklenmek üzere tasarlandı."""
    if chain != "BTC":
        return {"uygulanabilir": False, "gerekce": "Sadece BTC/BitcoinJS için geçerli"}

    ilk_tarih, tx_count = _ilk_islem_tarihini_bul(address)

    if ilk_tarih is None:
        if tx_count and tx_count > GUVENLI_TX_LIMITI:
            gerekce = f"Adres {tx_count} işlem içeriyor — güvenli sayfalama limitini ({GUVENLI_TX_LIMITI}) aşıyor, tarih tespiti güvenilir değil"
        else:
            gerekce = "İlk işlem tarihi tespit edilemedi"
        return {"uygulanabilir": False, "gerekce": gerekce, "tx_sayisi": tx_count}

    donem_icinde = RANDSTORM_START <= ilk_tarih <= RANDSTORM_END

    return {
        "uygulanabilir": True,
        "ilk_islem_tarihi": ilk_tarih.isoformat(),
        "tx_sayisi": tx_count,
        "randstorm_donemi_icinde": donem_icinde,
        "risk_katkisi": 25 if donem_icinde else 0,
        "gerekce": (
            "Zayıf RNG döneminde (2011-2015) ilk işlem — entropi riski mevcut"
            if donem_icinde else "Randstorm penceresi dışında"
        )
    }


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Kullanım: python3 sovereign_randstorm_scorer.py <address> [chain]")
        sys.exit(1)
    print(json.dumps(randstorm_riski(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "BTC"), indent=2, ensure_ascii=False))
