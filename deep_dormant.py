import requests, time
from datetime import datetime, timezone

def deep_dormant_analysis(address, max_sayfa=20):
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

if __name__ == "__main__":
    # Test için doğrudan dosyayı çalıştırdığımızda bu satır devreye girer
    deep_dormant_analysis('1FeexV6bAHb8ybZjqQMjJrcCrHGW9sb6uF')
