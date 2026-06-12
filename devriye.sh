#!/bin/bash
echo "🛡️ [SOVEREIGN NÖBET DEVRİYESİ BAŞLADI]"
echo "Durdurmak için Termux ekranında CTRL + C tuşlarına basabilirsiniz."
echo "--------------------------------------------------------"

# Dosya kontrolü
if [ ! -f ~/projeler/hedefler.txt ]; then
    echo "⚠️ HATA: hedefler.txt dosyası bulunamadı! Lütfen önce hedef adreslerinizi ekleyin."
    exit 1
fi

while true; do
    echo -e "\n🕒 Tarama Başlıyor: $(date)"
    
    # Motoru toplu tarama (-f) moduyla çalıştırıyoruz
    python3 ~/projeler/sovereign_scan.py -f ~/projeler/hedefler.txt --btc
    
    echo -e "\n💤 Tarama bitti. Radar 1 saat (3600 saniye) sessiz modda bekliyor..."
    sleep 3600
done
