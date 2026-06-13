#!/usr/bin/env python3
"""Sovereign Engine - Blockscout Forensics (key gerektirmez)"""
import argparse, json, time
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = "https://eth.blockscout.com/api/v2"
OUTPUT_DIR = Path.home() / "FORENSICS"

def get(endpoint, params=None):
    try:
        r = requests.get(f"{BASE}/{endpoint}", params=params, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def analyze(address):
    print(f"\n{'='*50}\n[ADRES] {address}\n{'='*50}")
    flags = []
    skor = 0

    # Adres bilgisi
    info = get(f"addresses/{address}")
    if "error" in info:
        print(f"  Hata: {info['error']}")
        return {}

    eth = int(info.get("coin_balance") or 0) / 1e18
    is_contract = info.get("is_contract", False)
    is_scam = info.get("is_scam", False)
    reputation = info.get("reputation", "unknown")

    print(f"  Bakiye    : {eth:.6f} ETH")
    print(f"  Contract  : {is_contract}")
    print(f"  Scam      : {is_scam}")
    print(f"  Reputation: {reputation}")

    if is_scam:
        flags.append("SCAM_TAGGED")
        skor += 50
    if reputation == "suspicious":
        flags.append("SUSPICIOUS_REPUTATION")
        skor += 30
    if eth < 0.001 and not is_contract:
        flags.append("KUCUK_BAKIYE")
        skor += 10

    # İşlem geçmişi
    txs = get(f"addresses/{address}/transactions", {"filter": "to|from"})
    tx_list = txs.get("items", [])
    print(f"  Tx sayısı : {len(tx_list)}")

    if tx_list:
        gelen = [t for t in tx_list if (t.get("to") or {}).get("hash","").lower() == address.lower()]
        giden = [t for t in tx_list if (t.get("from") or {}).get("hash","").lower() == address.lower()]
        print(f"  Gelen     : {len(gelen)} | Giden: {len(giden)}")

        if len(gelen) == 0 and len(giden) > 0:
            flags.append("SADECE_GIDEN")
            skor += 20

        # Hızlı transfer kontrolü
        hizli = 0
        for i in range(len(tx_list)-1):
            t1 = tx_list[i].get("timestamp","")
            t2 = tx_list[i+1].get("timestamp","")
            if t1 and t2:
                try:
                    d1 = datetime.fromisoformat(t1.replace("Z","+00:00"))
                    d2 = datetime.fromisoformat(t2.replace("Z","+00:00"))
                    if abs((d2-d1).total_seconds()) < 600:
                        hizli += 1
                except: pass
        if hizli > 2:
            flags.append("HIZLI_TRANSFER")
            skor += 25

    # Token transferleri
    tokens = get(f"addresses/{address}/token-transfers")
    token_count = len(tokens.get("items", []))
    print(f"  Token tx  : {token_count}")

    skor = min(skor, 100)
    seviye = ("KRİTİK 🔴" if skor>=70 else
              "YÜKSEK 🟠" if skor>=50 else
              "ORTA 🟡"   if skor>=30 else "DÜŞÜK 🟢")

    print(f"\n  {'─'*40}")
    print(f"  RİSK SKORU: {skor}/100 — {seviye}")
    if flags:
        print(f"  BAYRAKLAR : {', '.join(flags)}")
    print(f"  {'─'*40}")

    return {
        "adres": address,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_skoru": skor,
        "risk_seviyesi": seviye,
        "bayraklar": flags,
        "bakiye_eth": round(eth, 6),
        "is_contract": is_contract,
        "is_scam": is_scam,
        "reputation": reputation,
        "tx_sayisi": len(tx_list),
        "token_tx": token_count,
    }

def fund_flow(address, derinlik=2):
    print(f"\n[FUND FLOW] {address} (derinlik={derinlik})")
    goruldu = {address.lower()}
    mevcut = [address]
    katmanlar = []

    for k in range(derinlik):
        print(f"\n  Katman {k+1}:")
        sonraki = []
        katman_data = []
        for adres in mevcut:
            txs = get(f"addresses/{adres}/transactions")
            for t in txs.get("items", [])[:8]:
                kaynak = (t.get("from") or {}).get("hash","")
                hedef = (t.get("to") or {}).get("hash","")
                deger = int(t.get("value") or 0) / 1e18
                if deger < 0.001: continue
                karsi = hedef if kaynak.lower()==adres.lower() else kaynak
                if not karsi or karsi.lower() in goruldu: continue
                yon = "→" if kaynak.lower()==adres.lower() else "←"
                print(f"    {adres[:10]}... {yon} {karsi[:10]}... : {deger:.4f} ETH")
                katman_data.append({"kaynak":kaynak,"hedef":hedef,"deger_eth":round(deger,6),"hash":t.get("hash","")})
                goruldu.add(karsi.lower())
                sonraki.append(karsi)
        katmanlar.append(katman_data)
        mevcut = sonraki[:5]
        time.sleep(0.5)

    return {"kok": address, "katmanlar": katmanlar}

def save(address, data):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe = address[:10].replace("0x","").lower()
    f = OUTPUT_DIR / f"blockscout_{safe}_{ts}.json"
    with open(f,"w") as fp:
        json.dump(data, fp, indent=2, default=str)
    print(f"\n✅ Rapor: {f}")

def main():
    ap = argparse.ArgumentParser(description="Sovereign Engine - Blockscout Forensics")
    ap.add_argument("-a","--address", required=True)
    ap.add_argument("--flow", action="store_true")
    ap.add_argument("--depth", type=int, default=2)
    args = ap.parse_args()

    report = {"adres": args.address, "timestamp": datetime.now(timezone.utc).isoformat()}
    report["risk"] = analyze(args.address)
    if args.flow:
        report["fund_flow"] = fund_flow(args.address, args.depth)
    save(args.address, report)

if __name__ == "__main__":
    main()

# ─── BITCOIN DESTEĞİ ─────────────────────────────────────────────────────────

def analyze_btc(address):
    print(f"\n{'='*50}\n[BTC ADRES] {address}\n{'='*50}")
    flags = []
    skor = 0

    try:
        r = requests.get(
            f"https://blockchain.info/rawaddr/{address}?limit=50",
            timeout=10
        )
        data = r.json()
    except Exception as e:
        print(f"  Hata: {e}")
        return {"error": str(e)}

    btc = data.get("final_balance", 0) / 1e8
    tx_count = data.get("n_tx", 0)
    total_recv = data.get("total_received", 0) / 1e8
    total_sent = data.get("total_sent", 0) / 1e8
    txs = data.get("txs", [])

    print(f"  Bakiye    : {btc:.8f} BTC")
    print(f"  Tx sayısı : {tx_count}")
    print(f"  Toplam al : {total_recv:.8f} BTC")
    print(f"  Toplam ver: {total_sent:.8f} BTC")

    if btc < 0.0001:
        flags.append("KUCUK_BAKIYE")
        skor += 10

    if total_sent == 0 and tx_count > 0:
        flags.append("SADECE_GELEN")
        skor += 15

    # Hızlı transfer kontrolü
    hizli = 0
    for i in range(len(txs)-1):
        t1 = txs[i].get("time", 0)
        t2 = txs[i+1].get("time", 0)
        if t1 and t2 and abs(t1-t2) < 600:
            hizli += 1
    if hizli > 2:
        flags.append("HIZLI_TRANSFER")
        skor += 25

    # Benzersiz adres sayısı
    adresler = set()
    for t in txs:
        for inp in t.get("inputs", []):
            a = inp.get("prev_out", {}).get("addr")
            if a: adresler.add(a)
        for out in t.get("out", []):
            a = out.get("addr")
            if a: adresler.add(a)
    adresler.discard(address)
    print(f"  Karşı taraf: {len(adresler)} benzersiz adres")

    skor = min(skor, 100)
    seviye = ("KRİTİK 🔴" if skor>=70 else
              "YÜKSEK 🟠" if skor>=50 else
              "ORTA 🟡"   if skor>=30 else "DÜŞÜK 🟢")

    print(f"\n  {'─'*40}")
    print(f"  RİSK SKORU: {skor}/100 — {seviye}")
    if flags:
        print(f"  BAYRAKLAR : {', '.join(flags)}")
    print(f"  {'─'*40}")

    return {
        "adres": address, "zincir": "BTC",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_skoru": skor, "risk_seviyesi": seviye,
        "bayraklar": flags, "bakiye_btc": round(btc, 8),
        "tx_sayisi": tx_count, "benzersiz_adres": len(adresler),
    }

def analyze_btc_blockstream(address):
    print(f"\n{'='*50}\n[BTC] {address}\n{'='*50}")
    flags = []
    skor = 0
    try:
        r = requests.get(
            f"https://blockstream.info/api/address/{address}",
            timeout=10
        )
        data = r.json()
    except Exception as e:
        print(f"  Hata: {e}")
        return {"error": str(e)}

    funded = data.get("chain_stats", {}).get("funded_txo_sum", 0) / 1e8
    spent = data.get("chain_stats", {}).get("spent_txo_sum", 0) / 1e8
    btc = funded - spent
    tx_count = data.get("chain_stats", {}).get("tx_count", 0)

    print(f"  Bakiye    : {btc:.8f} BTC")
    print(f"  Tx sayısı : {tx_count}")
    print(f"  Toplam al : {funded:.8f} BTC")
    print(f"  Toplam ver: {spent:.8f} BTC")

    if btc < 0.0001 and tx_count > 0:
        flags.append("KUCUK_BAKIYE"); skor += 10
    if spent == 0 and tx_count > 0:
        flags.append("SADECE_GELEN"); skor += 15
    if tx_count > 500:
        flags.append("YUKSEK_TX"); skor += 10

    skor = min(skor, 100)
    seviye = ("KRİTİK 🔴" if skor>=70 else
              "YÜKSEK 🟠" if skor>=50 else
              "ORTA 🟡"   if skor>=30 else "DÜŞÜK 🟢")

    print(f"\n  {'─'*40}")
    print(f"  RİSK SKORU: {skor}/100 — {seviye}")
    if flags: print(f"  BAYRAKLAR : {', '.join(flags)}")
    print(f"  {'─'*40}")

    return {
        "adres": address, "zincir": "BTC",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_skoru": skor, "risk_seviyesi": seviye,
        "bayraklar": flags, "bakiye_btc": round(btc, 8),
        "tx_sayisi": tx_count,
    }

def advanced_risk(address, tx_data):
    """Gelişmiş risk kalıpları tespiti"""
    flags = []
    skor = 0
    txs = tx_data.get("items", [])
    if not txs:
        return flags, skor

    values = []
    timestamps = []

    for t in txs:
        v = int(t.get("value") or 0) / 1e8
        ts = t.get("timestamp", "")
        if v > 0:
            values.append(v)
        if ts:
            try:
                from datetime import datetime, timezone
                d = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                timestamps.append(d.timestamp())
            except:
                pass

    # Peel chain: sürekli azalan miktarlar
    if len(values) >= 5:
        azalan = sum(1 for i in range(len(values)-1)
                     if values[i] > values[i+1])
        if azalan > len(values) * 0.7:
            flags.append("PEEL_CHAIN")
            skor += 30

    # Round number: yuvarlak miktarlar
    if values:
        round_count = sum(1 for v in values if v == int(v) and v > 0)
        if round_count > len(values) * 0.5:
            flags.append("ROUND_NUMBER")
            skor += 15

    # Hızlı transfer: ardışık tx arası < 10 dakika
    if len(timestamps) >= 3:
        hizli = sum(1 for i in range(len(timestamps)-1)
                    if abs(timestamps[i]-timestamps[i+1]) < 600)
        if hizli > 2:
            flags.append("HIZLI_TRANSFER")
            skor += 25

    # Fan-out: çok sayıda farklı alıcı
    hedefler = set()
    for t in txs:
        h = (t.get("to") or {}).get("hash", "")
        if h and h.lower() != address.lower():
            hedefler.add(h.lower())
    if len(hedefler) > 20 and len(txs) < 50:
        flags.append("FAN_OUT")
        skor += 20

    # Dust: çok küçük miktarlar
    if values:
        dust = sum(1 for v in values if 0 < v < 0.0001)
        if dust > len(values) * 0.3:
            flags.append("DUST_ATTACK")
            skor += 20

    return flags, min(skor, 100)

def fund_flow_btc(address, derinlik=2):
    print(f"\n[BTC FUND FLOW] {address} (derinlik={derinlik})")
    import time
    goruldu = {address}
    mevcut = [address]
    katmanlar = []

    for k in range(derinlik):
        print(f"\n  Katman {k+1}:")
        sonraki = []
        katman_data = []

        for adres in mevcut:
            try:
                r = requests.get(
                    f"https://blockstream.info/api/address/{adres}/txs",
                    timeout=10
                )
                txs = r.json()
            except:
                continue

            for t in txs[:5]:
                # Girdiler
                for inp in t.get("vin", []):
                    prev = inp.get("prevout", {})
                    kaynak = prev.get("scriptpubkey_address", "")
                    deger = prev.get("value", 0) / 1e8
                    if not kaynak or kaynak in goruldu or deger < 0.01:
                        continue
                    print(f"    {kaynak[:12]}... → {adres[:12]}... : {deger:.4f} BTC")
                    katman_data.append({
                        "kaynak": kaynak, "hedef": adres,
                        "deger_btc": round(deger, 8),
                        "txid": t.get("txid", "")
                    })
                    goruldu.add(kaynak)
                    sonraki.append(kaynak)

                # Çıktılar
                for out in t.get("vout", []):
                    hedef = out.get("scriptpubkey_address", "")
                    deger = out.get("value", 0) / 1e8
                    if not hedef or hedef in goruldu or deger < 0.01:
                        continue
                    if hedef != adres:
                        print(f"    {adres[:12]}... → {hedef[:12]}... : {deger:.4f} BTC")
                        katman_data.append({
                            "kaynak": adres, "hedef": hedef,
                            "deger_btc": round(deger, 8),
                            "txid": t.get("txid", "")
                        })
                        goruldu.add(hedef)
                        sonraki.append(hedef)

            time.sleep(0.3)

        katmanlar.append(katman_data)
        mevcut = sonraki[:3]

    return {"kok": address, "katmanlar": katmanlar}

def dormant_analysis(address):
    """Dormant adres aktivasyon analizi"""
    print(f"\n[DORMANT ANALİZ] {address}")
    
    import requests
    from datetime import datetime, timezone
    
    try:
        r = requests.get(
            f"https://blockstream.info/api/address/{address}/txs",
            timeout=10
        )
        txs = r.json()
    except Exception as e:
        return {"error": str(e)}

    if not txs:
        return {"durum": "tx_yok"}

    zamanlar = []
    for t in txs:
        bt = t.get("status", {}).get("block_time", 0)
        if bt:
            zamanlar.append(bt)

    if len(zamanlar) < 2:
        return {"durum": "yetersiz_veri"}

    zamanlar.sort()
    ilk = zamanlar[0]
    son = zamanlar[-1]

    bosluklar = []
    for i in range(len(zamanlar) - 1):
        fark_gun = (zamanlar[i+1] - zamanlar[i]) / 86400
        if fark_gun > 180:  # 6 aydan uzun bosluk
            bosluklar.append({
                "baslangic": datetime.fromtimestamp(zamanlar[i], timezone.utc).strftime("%Y-%m-%d"),
                "bitis": datetime.fromtimestamp(zamanlar[i+1], timezone.utc).strftime("%Y-%m-%d"),
                "sure_gun": round(fark_gun)
            })

    ilk_tarih = datetime.fromtimestamp(ilk, timezone.utc).strftime("%Y-%m-%d")
    son_tarih = datetime.fromtimestamp(son, timezone.utc).strftime("%Y-%m-%d")
    toplam_gun = (son - ilk) / 86400

    print(f"  İlk aktivite : {ilk_tarih}")
    print(f"  Son aktivite : {son_tarih}")
    print(f"  Toplam süre  : {toplam_gun:.0f} gün ({toplam_gun/365:.1f} yıl)")
    print(f"  Uzun boşluk  : {len(bosluklar)} adet (>180 gün)")
    
    for b in bosluklar:
        print(f"    {b['baslangic']} → {b['bitis']} : {b['sure_gun']} gün")

    return {
        "adres": address,
        "ilk_aktivite": ilk_tarih,
        "son_aktivite": son_tarih,
        "toplam_gun": round(toplam_gun),
        "uzun_bosluklar": bosluklar
    }



def deep_dormant(address, max_sayfa=20):
    print(f"\n[🔍 DERİN DORMANT ANALİZ] {address}")
    print("  API sayfalama (pagination) başlatılıyor...")
    
    txs = []
    last_txid = None
    
    # max_sayfa limiti, on binlerce işlemi olan cüzdanlarda sistemin kilitlenmesini önler
    for sayfa in range(max_sayfa):
        # Eğer ilk sayfa değilse, url'nin sonuna last_txid eklenir
        if last_txid:
            url = f"https://blockstream.info/api/address/{address}/txs/chain/{last_txid}"
        else:
            url = f"https://blockstream.info/api/address/{address}/txs"
            
        try:
            r = requests.get(url, timeout=10)
            if r.status_code != 200:
                print(f"  ⚠️ API yanıt vermedi (Durum: {r.status_code}). Döngü durduruluyor.")
                break
            sayfa_txs = r.json()
        except Exception as e:
            print(f"  ⚠️ Bağlantı hatası: {e}")
            break
            
        if not sayfa_txs:
            break  # Sayfada işlem kalmadıysa (kök işleme ulaşıldıysa) döngüyü kır
            
        txs.extend(sayfa_txs)
        last_txid = sayfa_txs[-1]["txid"]
        
        print(f"  Sayfa {sayfa+1} okundu. Toplam çekilen işlem: {len(txs)}")
        
        # Sunucuyu yormamak ve IP ban yememek için 0.5 saniye mola
        time.sleep(0.5)

    if not txs:
        print("  ❌ İşlem bulunamadı.")
        return

    # Sadece blok onayı almış (block_time içeren) işlemleri filtrele
    zamanlar = [t["status"]["block_time"] for t in txs if t.get("status", {}).get("block_time")]
    
    if len(zamanlar) < 2:
        print("  ⚠️ Analiz için yeterli onaylanmış işlem yok.")
        return

    # Tarihleri eskiye (2011'e) doğru çekeceğimiz için kronolojik olarak sıralayalım
    zamanlar.sort()
    ilk = zamanlar[0]
    son = zamanlar[-1]

    bosluklar = []
    for i in range(len(zamanlar) - 1):
        fark_gun = (zamanlar[i+1] - zamanlar[i]) / 86400
        if fark_gun > 180:  # 180 günden uzun uyku süreleri
            bosluklar.append({
                "baslangic": datetime.fromtimestamp(zamanlar[i], timezone.utc).strftime("%Y-%m-%d"),
                "bitis": datetime.fromtimestamp(zamanlar[i+1], timezone.utc).strftime("%Y-%m-%d"),
                "sure_gun": round(fark_gun)
            })

    ilk_tarih = datetime.fromtimestamp(ilk, timezone.utc).strftime("%Y-%m-%d")
    son_tarih = datetime.fromtimestamp(son, timezone.utc).strftime("%Y-%m-%d")
    toplam_gun = (son - ilk) / 86400

    print(f"\n📊 [ANALİZ SONUCU]")
    print(f"  Taranan İşlem: {len(txs)} (Son {max_sayfa} sayfa limitiyle)")
    print(f"  İlk Aktivite : {ilk_tarih}")
    print(f"  Son Aktivite : {son_tarih}")
    print(f"  Toplam Süre  : {toplam_gun:.0f} gün ({toplam_gun/365:.1f} yıl)")
    print(f"  Uzun Boşluk  : {len(bosluklar)} adet (>180 gün)")
    
    for b in bosluklar:
        print(f"    🚩 {b['baslangic']} → {b['bitis']} : {b['sure_gun']} gün uyku modunda")

def risk_v2(address, chain="ETH"):
    """Gelişmiş risk motoru v2 — yeni kurallar"""
    import requests, time
    flags = []
    skor = 0
    detay = {}

    if chain == "BTC":
        try:
            r = requests.get(
                f"https://blockstream.info/api/address/{address}",
                timeout=10
            )
            if r.status_code != 200:
                return {"error": f"API {r.status_code}"}
            d = r.json()
            cs = d.get("chain_stats", {})
            funded = cs.get("funded_txo_sum", 0) / 1e8
            spent = cs.get("spent_txo_sum", 0) / 1e8
            bakiye = funded - spent
            tx_count = cs.get("tx_count", 0)
            utxo_count = cs.get("funded_txo_count", 0)

            detay = {
                "bakiye_btc": round(bakiye, 8),
                "tx_sayisi": tx_count,
                "utxo_sayisi": utxo_count,
                "toplam_girdi": round(funded, 8),
                "toplam_cikti": round(spent, 8),
            }

            # Kural 1: Kucuk bakiye
            if bakiye < 0.0001 and tx_count > 0:
                flags.append("KUCUK_BAKIYE"); skor += 10

            # Kural 2: Sadece gelen
            if spent == 0 and tx_count > 5:
                flags.append("SADECE_GELEN"); skor += 15

            # Kural 3: Yuksek tx
            if tx_count > 500:
                flags.append("YUKSEK_TX"); skor += 10

            # Kural 4: Cok fazla UTXO — mixing sonrası patern
            if utxo_count > 100:
                flags.append("COK_UTXO"); skor += 20

            # Kural 5: Yuvarlak bakiye — tam BTC'ler
            if bakiye > 0 and bakiye == int(bakiye):
                flags.append("YUVARLAK_BAKIYE"); skor += 15

            # Kural 6: Yuksek hacim dusuk bakiye
            if funded > 1000 and bakiye < 0.01:
                flags.append("YUKSEK_HACIM_BOSTA"); skor += 25

            # Kural 7: tx başına ortalama deger
            if tx_count > 0:
                ort = funded / tx_count
                detay["ortalama_tx_btc"] = round(ort, 8)
                if ort < 0.001:
                    flags.append("MIKRO_TX_PATERNI"); skor += 15

        except Exception as e:
            return {"error": str(e)}

    skor = min(skor, 100)
    seviye = ("KRİTİK 🔴" if skor >= 70 else
              "YÜKSEK 🟠" if skor >= 50 else
              "ORTA 🟡"   if skor >= 30 else "DÜŞÜK 🟢")

    print(f"\n[RİSK V2] {address[:20]}...")
    print(f"  Bakiye    : {detay.get('bakiye_btc', '?')} BTC")
    print(f"  Tx        : {detay.get('tx_sayisi', '?')}")
    print(f"  UTXO      : {detay.get('utxo_sayisi', '?')}")
    print(f"  Ort tx    : {detay.get('ortalama_tx_btc', '?')} BTC")
    print(f"  Skor      : {skor}/100 — {seviye}")
    if flags:
        print(f"  Bayraklar : {', '.join(flags)}")

    return {
        "adres": address,
        "zincir": chain,
        "risk_skoru": skor,
        "risk_seviyesi": seviye,
        "bayraklar": flags,
        "detay": detay
    }

def etherscan_analyze(address):
    """Etherscan V2 ile derin ETH analizi"""
    import requests, re
    from datetime import datetime, timezone

    key = open('/data/data/com.termux/files/home/.env_keys').read()
    k = re.search('ETHERSCAN_KEY=(.*)', key).group(1).strip()

    def es(module, action, extra={}):
        r = requests.get('https://api.etherscan.io/v2/api', params={
            'chainid': '1', 'module': module,
            'action': action, 'address': address,
            'apikey': k, **extra
        }, timeout=10)
        return r.json()

    print(f"\n[ETHERSCAN] {address[:20]}...")
    flags = []
    skor = 0

    # Bakiye
    bal = es('account', 'balance', {'tag': 'latest'})
    eth = int(bal.get('result', 0)) / 1e18
    print(f"  Bakiye    : {eth:.6f} ETH")

    # Normal tx
    txs = es('account', 'txlist', {'startblock': 0, 'endblock': 99999999, 'sort': 'asc', 'page': 1, 'offset': 100})
    tx_list = txs.get('result', [])

    if isinstance(tx_list, list) and len(tx_list) > 0:
        print(f"  Tx sayısı : {len(tx_list)}")
        first_ts = int(tx_list[0]['timeStamp'])
        last_ts = int(tx_list[-1]['timeStamp'])
        first_date = datetime.fromtimestamp(first_ts, timezone.utc).strftime('%Y-%m-%d')
        last_date = datetime.fromtimestamp(last_ts, timezone.utc).strftime('%Y-%m-%d')
        print(f"  İlk tx    : {first_date}")
        print(f"  Son tx    : {last_date}")

        # Dormant kontrolü
        gun = (last_ts - first_ts) / 86400
        if gun > 365:
            flags.append("UZUN_SURELI_AKTIF")
            skor += 5

        # Hızlı transfer
        hizli = 0
        for i in range(len(tx_list) - 1):
            sure = int(tx_list[i+1]['timeStamp']) - int(tx_list[i]['timeStamp'])
            if sure < 600:
                hizli += 1
        if hizli > 3:
            flags.append("HIZLI_TRANSFER")
            skor += 25
            print(f"  ⚠️ Hızlı transfer: {hizli} adet")

        # Gelen/giden
        gelen = [t for t in tx_list if t['to'].lower() == address.lower()]
        giden = [t for t in tx_list if t['from'].lower() == address.lower()]
        print(f"  Gelen/Giden: {len(gelen)}/{len(giden)}")
        if len(gelen) == 0 and len(giden) > 0:
            flags.append("SADECE_GIDEN"); skor += 20

    # Internal tx
    itxs = es('account', 'txlistinternal', {'page': 1, 'offset': 50})
    i_list = itxs.get('result', [])
    if isinstance(i_list, list):
        print(f"  Internal  : {len(i_list)} tx")

    # ERC20 transferler
    tokens = es('account', 'tokentx', {'page': 1, 'offset': 50})
    t_list = tokens.get('result', [])
    if isinstance(t_list, list):
        token_symbols = set(t['tokenSymbol'] for t in t_list)
        print(f"  Tokenlar  : {', '.join(list(token_symbols)[:5])}")

    skor = min(skor, 100)
    seviye = ("KRİTİK 🔴" if skor >= 70 else
              "YÜKSEK 🟠" if skor >= 50 else
              "ORTA 🟡"   if skor >= 30 else "DÜŞÜK 🟢")

    print(f"  Risk      : {skor}/100 — {seviye}")
    if flags:
        print(f"  Bayraklar : {', '.join(flags)}")

    return {
        "adres": address, "bakiye_eth": round(eth, 6),
        "tx_sayisi": len(tx_list) if isinstance(tx_list, list) else 0,
        "risk_skoru": skor, "risk_seviyesi": seviye, "bayraklar": flags
    }
