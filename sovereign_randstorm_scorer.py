#!/usr/bin/env python3
"""
sovereign_randstorm_scorer.py — Randstorm RNG Zafiyeti Tespiti (v2)
2011-2015 arası BitcoinJS tabanlı cüzdanlarda zayıf tarayıcı RNG riski.
Referans: Unciphered "Randstorm" araştırması (2023).

v2 eklentileri: adres tipi filtresi, bakiye/aciliyet kontrolü,
alt-dönem ağırlıklandırma, mempool.space fallback, toplu tarama.
"""

import requests
import time
from datetime import datetime, timezone

RANDSTORM_START = datetime(2011, 1, 1, tzinfo=timezone.utc)
RANDSTORM_END = datetime(2015, 12, 31, tzinfo=timezone.utc)
YUKSEK_RISK_START = datetime(2011, 1, 1, tzinfo=timezone.utc)
YUKSEK_RISK_END = datetime(2012, 6, 30, tzinfo=timezone.utc)

GUVENLI_TX_LIMITI = 5000
API_ROOTS = ["https://blockstream.info/api", "https://mempool.space/api"]
MAX_RETRY = 3
RETRY_BEKLEME = 2


def _get_with_retry(path: str):
    for root in API_ROOTS:
        bekleme = RETRY_BEKLEME
        for _ in range(MAX_RETRY):
            try:
                r = requests.get(root + path, timeout=10)
                if r.status_code == 200:
                    return r.json()
            except Exception:
                pass
            time.sleep(bekleme)
            bekleme *= 2
    return None


def _adres_tipi(address: str) -> str:
    if address.startswith("1"):
        return "P2PKH (legacy)"
    if address.startswith("3"):
        return "P2SH (legacy/multisig)"
    if address.startswith("bc1q"):
        return "P2WPKH/P2WSH (native segwit)"
    if address.startswith("bc1p"):
        return "P2TR (taproot)"
    return "bilinmeyen"


def _bakiye_ve_tx_bilgisi(address: str):
    stats = _get_with_retry(f"/address/{address}")
    if stats is None:
        return None
    chain = stats.get("chain_stats", {})
    mempool = stats.get("mempool_stats", {})
    tx_count = chain.get("tx_count", 0) + mempool.get("tx_count", 0)
    bakiye = (
        chain.get("funded_txo_sum", 0) - chain.get("spent_txo_sum", 0)
        + mempool.get("funded_txo_sum", 0) - mempool.get("spent_txo_sum", 0)
    )
    return {"tx_count": tx_count, "bakiye_satoshi": bakiye}


def _ilk_islem_tarihini_bul(address: str, tx_count: int):
    if tx_count > GUVENLI_TX_LIMITI:
        return None

    last_txid = None
    son_sayfa = None
    max_sayfa = (tx_count // 25) + 2

    for _ in range(max_sayfa):
        path = f"/address/{address}/txs/chain" if last_txid is None else f"/address/{address}/txs/chain/{last_txid}"
        txs = _get_with_retry(path)
        if not txs:
            break
        son_sayfa = txs
        if len(txs) < 25:
            break
        last_txid = txs[-1]["txid"]

    if not son_sayfa:
        return None

    confirmed = [t for t in son_sayfa if t.get("status", {}).get("confirmed")]
    if not confirmed:
        return None

    oldest = min(t["status"]["block_time"] for t in confirmed)
    return datetime.fromtimestamp(oldest, tz=timezone.utc)


def randstorm_riski(address: str, chain: str = "BTC") -> dict:
    if chain != "BTC":
        return {"uygulanabilir": False, "gerekce": "Sadece BTC/BitcoinJS için geçerli"}

    adres_tipi = _adres_tipi(address)
    if adres_tipi in ("P2WPKH/P2WSH (native segwit)", "P2TR (taproot)"):
        return {
            "uygulanabilir": False,
            "gerekce": f"{adres_tipi} formatı Randstorm döneminden sonra standartlaştı, uygulanabilir değil",
            "adres_tipi": adres_tipi,
        }

    bilgi = _bakiye_ve_tx_bilgisi(address)
    if bilgi is None:
        return {"uygulanabilir": False, "gerekce": "API'lerden veri alınamadı (blockstream.info + mempool.space başarısız)", "adres_tipi": adres_tipi}

    tx_count = bilgi["tx_count"]
    if tx_count > GUVENLI_TX_LIMITI:
        return {
            "uygulanabilir": False,
            "gerekce": f"Adres {tx_count} işlem içeriyor — güvenli sayfalama limitini ({GUVENLI_TX_LIMITI}) aşıyor",
            "tx_sayisi": tx_count,
            "adres_tipi": adres_tipi,
        }

    ilk_tarih = _ilk_islem_tarihini_bul(address, tx_count)
    if ilk_tarih is None:
        return {"uygulanabilir": False, "gerekce": "İlk işlem tarihi tespit edilemedi", "tx_sayisi": tx_count, "adres_tipi": adres_tipi}

    donem_icinde = RANDSTORM_START <= ilk_tarih <= RANDSTORM_END
    yuksek_risk = YUKSEK_RISK_START <= ilk_tarih <= YUKSEK_RISK_END

    if not donem_icinde:
        risk_katkisi, gerekce = 0, "Randstorm penceresi dışında"
    elif yuksek_risk:
        risk_katkisi, gerekce = 35, "En yüksek riskli alt-dönemde (2011 - 2012 ortası) ilk işlem"
    else:
        risk_katkisi, gerekce = 20, "Randstorm döneminde (2012 sonu - 2015) ilk işlem"

    return {
        "uygulanabilir": True,
        "adres_tipi": adres_tipi,
        "ilk_islem_tarihi": ilk_tarih.isoformat(),
        "tx_sayisi": tx_count,
        "bakiye_satoshi": bilgi["bakiye_satoshi"],
        "randstorm_donemi_icinde": donem_icinde,
        "yuksek_risk_alt_donem": yuksek_risk,
        "risk_katkisi": risk_katkisi,
        "aciliyet_fon_hala_duruyor": donem_icinde and bilgi["bakiye_satoshi"] > 0,
        "gerekce": gerekce,
    }


def toplu_randstorm_taramasi(adres_listesi: list, chain: str = "BTC", bekleme_sn: float = 0.5) -> list:
    sonuclar = []
    for adres in adres_listesi:
        sonuc = randstorm_riski(adres, chain)
        sonuc["adres"] = adres
        sonuclar.append(sonuc)
        time.sleep(bekleme_sn)
    return sonuclar


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 2:
        print("Kullanım:")
        print("  Tekil:  python3 sovereign_randstorm_scorer.py <address> [chain]")
        print("  Toplu:  python3 sovereign_randstorm_scorer.py --batch <dosya.txt>")
        sys.exit(1)

    if sys.argv[1] == "--batch":
        with open(sys.argv[2]) as f:
            adresler = [l.strip() for l in f if l.strip()]
        print(json.dumps(toplu_randstorm_taramasi(adresler), indent=2, ensure_ascii=False))
    else:
        print(json.dumps(randstorm_riski(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "BTC"), indent=2, ensure_ascii=False))
