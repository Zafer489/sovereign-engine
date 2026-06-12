import os
import re

def scan_secrets(directory):
    print(f"\n[🛡️ SOVEREIGN LEAKS] Klasör taranıyor: {directory}\n")
    
    # Aranacak hassas veri paternleri (Regex)
    patterns = {
        "Telegram Bot Token": r"[0-9]{9,10}:[a-zA-Z0-9_-]{35}",
        "Private Key (Hex)": r"(?i)(?:private[_\s]?key|secret).{0,20}['\"]?([0-9a-f]{64})['\"]?",
        "Binance/Borsa API Key": r"(?i)(?:api[_\s]?key|access[_\s]?key).{0,20}['\"]?([a-zA-Z0-9]{64})['\"]?",
        "Mnemonic (Seed Phrase)": r"(?i)(?:mnemonic|seed phrase).{0,20}['\"]?([a-z ]{40,250})['\"]?"
    }

    found_leaks = False
    
    # Klasördeki tüm dosyaları tara (gizli dizinler ve env hariç)
    for root, dirs, files in os.walk(directory):
        # .git, __pycache__ gibi klasörleri atla
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for file in files:
            # .env_keys dosyamız zaten şifreleri tuttuğu için onu taramaya gerek yok
            if file == ".env_keys" or file.endswith(".pyc"):
                continue
                
            filepath = os.path.join(root, file)
            
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                    for secret_name, regex_pattern in patterns.items():
                        matches = re.finditer(regex_pattern, content)
                        for match in matches:
                            found_leaks = True
                            # Şifrenin tamamını ekrana basmamak için maskeleme yapıyoruz
                            secret = match.group(0)
                            masked_secret = secret[:5] + "..." + secret[-5:] if len(secret) > 10 else secret
                            
                            print(f"  🚨 SIZINTI TESPİT EDİLDİ: {secret_name}")
                            print(f"  📄 Dosya: {filepath}")
                            print(f"  🔑 Eşleşme: {masked_secret}")
                            print("-" * 50)
            except Exception as e:
                pass

    if not found_leaks:
        print("  ✅ Harika! Kodlarınız temiz, hiçbir hassas veri sızıntısı bulunamadı.")

if __name__ == "__main__":
    scan_secrets("/data/data/com.termux/files/home/projeler")
