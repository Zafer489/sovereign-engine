#!/usr/bin/env python3
"""
Sovereign Engine - Risk Kalibrasyon Modülü
Bilinen exchange adresleri ile baseline oluşturur
"""

import json
from pathlib import Path

# Kamuya açık, doğrulanmış exchange adresleri
WHITELIST = {
    # Binance cold wallets
    "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo": "Binance Cold Wallet",
    "bc1qm34lsc65zpw79lxes69zkqmk6ee3ewf0j77s3h": "Binance Hot Wallet",
    # Coinbase
    "3FHNBLobJnbCPGMBundle4QDYgJAQMBUrGh": "Coinbase",
    # Kraken
    "bc1qr4dl5wa7kl8yu792dceg9z5knl2gkn220lk7a9": "Kraken",
    # ETH exchange contracts
    "0x3f5CE5FBFe3E9af3971dD833D26bA9b5C936f0bE": "Binance ETH Hot",
    "0x47ac0Fb4F2D84898e4D9E7b4DaB3C24507a6D503": "Binance Cold ETH",
}

WATCHLIST_OFAC = [
    # OFAC yaptırım listesinden kamuya açık adresler
    "0x7F367cC41522cE07553e823bf3be79A889debe1B",  # Lazarus Group
    "0xd882cFc20F52f2599D84b8e8D58C7FB62cfE344b",  # Lazarus Group
]

def kalibrasyon_skoru(adres: str, ham_skor: int) -> dict:
    """
    Ham risk skorunu kalibre et:
    - Whitelist'teyse skoru düşür
    - OFAC listesindeyse skoru maksimize et
    """
    adres_lower = adres.lower()

    # OFAC kontrolü
    for ofac in WATCHLIST_OFAC:
        if adres_lower == ofac.lower():
            return {
                "kalibre_skor": 100,
                "etiket": "OFAC_SANCTIONED 🚫",
                "aciklama": "OFAC yaptırım listesinde"
            }

    # Whitelist kontrolü
    for wl_adres, isim in WHITELIST.items():
        if adres_lower == wl_adres.lower():
            return {
                "kalibre_skor": max(0, ham_skor - 30),
                "etiket": f"BILINEN_EXCHANGE: {isim}",
                "aciklama": f"Tanınan exchange adresi — {isim}"
            }

    # Normal adres
    return {
        "kalibre_skor": ham_skor,
        "etiket": "BILINMIYOR",
        "aciklama": "Exchange listesinde yok"
    }

def whitelist_goster():
    print("\n[WHITELIST] Bilinen exchange adresleri:")
    for adres, isim in WHITELIST.items():
        print(f"  {isim:30} {adres[:20]}...")

    print("\n[OFAC] Yaptırım listesi:")
    for adres in WATCHLIST_OFAC:
        print(f"  🚫 {adres[:30]}...")

if __name__ == "__main__":
    whitelist_goster()

    # Test
    test_adresler = [
        "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo",
        "0x7F367cC41522cE07553e823bf3be79A889debe1B",
        "1Hr5B4sX2U7HtB3erZq4b7mbdJgpM7EsFc",
    ]

    print("\n[TEST] Kalibrasyon:")
    for adres in test_adresler:
        sonuc = kalibrasyon_skoru(adres, 30)
        print(f"  {adres[:20]}... → {sonuc['kalibre_skor']}/100 | {sonuc['etiket']}")
