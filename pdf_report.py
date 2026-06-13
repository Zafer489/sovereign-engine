#!/usr/bin/env python3
"""Sovereign Engine - PDF Rapor Üretici"""

from fpdf import FPDF
from datetime import datetime, timezone
from pathlib import Path
import json, glob

FORENSICS_DIR = Path.home() / "FORENSICS"
PDF_DIR = Path.home() / "FORENSICS" / "pdf_raporlar"

class SovereignPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "Sovereign Engine - Forensics Raporu", align="C")
        self.ln(5)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, f"Tarih: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC", align="C")
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Sayfa {self.page_no()} | Yalnizca arastirma amaclidir", align="C")

def generate_pdf(json_dosya=None):
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    pdf = SovereignPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Veri yükle
    if json_dosya:
        with open(json_dosya) as f:
            data = json.load(f)
        raporlar = [data]
    else:
        raporlar = []
        for f in sorted(glob.glob(str(FORENSICS_DIR / "*.json")))[-10:]:
            try:
                with open(f) as fp:
                    raporlar.append(json.load(fp))
            except: pass

    # Özet bölümü
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(30, 30, 60)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, "  OZET", fill=True)
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Toplam rapor: {len(raporlar)}")
    pdf.ln(6)

    # Her raporu ekle
    for r in raporlar:
        adres = r.get("adres", r.get("target", "Bilinmiyor"))
        if not adres or adres == "None":
            continue

        # Adres başlığı
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(200, 220, 255)
        pdf.cell(0, 7, f"  Adres: {str(adres)[:50]}", fill=True)
        pdf.ln(2)

        # Risk bilgisi
        risk = r.get("risk_analizi", r.get("risk", {}))
        if risk:
            skor = risk.get("risk_skoru", 0)
            seviye = risk.get("risk_seviyesi", "?")
            bayraklar = ", ".join(risk.get("bayraklar", [])) or "Yok"

            # Risk rengi
            if skor >= 70:
                pdf.set_fill_color(255, 100, 100)
            elif skor >= 50:
                pdf.set_fill_color(255, 180, 100)
            elif skor >= 30:
                pdf.set_fill_color(255, 255, 100)
            else:
                pdf.set_fill_color(100, 255, 100)

            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(60, 6, f"Risk Skoru: {skor}/100", fill=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"  {seviye}")
            pdf.ln(5)

            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 5, f"Bayraklar: {bayraklar}")
            pdf.ln(4)

            # Detaylar
            detay = risk.get("detaylar", {})
            if detay:
                for k, v in list(detay.items())[:5]:
                    pdf.cell(0, 4, f"  {k}: {v}")
                    pdf.ln(3)

        # Fund flow özeti
        flow = r.get("fund_flow", {})
        if flow and flow.get("katmanlar"):
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, "Fund Flow:")
            pdf.ln(3)
            pdf.set_font("Helvetica", "", 8)
            for i, katman in enumerate(flow["katmanlar"][:2]):
                for tx in katman[:3]:
                    line = f"  K{i+1}: {str(tx.get('kaynak',''))[:15]}... -> {str(tx.get('hedef',''))[:15]}... : {tx.get('deger_eth', tx.get('deger_btc', '?'))} ETH/BTC"
                    pdf.cell(0, 4, line)
                    pdf.ln(3)

        pdf.ln(4)
        pdf.set_draw_color(150, 150, 150)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

    # Kaydet
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dosya = PDF_DIR / f"sovereign_rapor_{ts}.pdf"
    pdf.output(str(dosya))
    print(f"PDF rapor: {dosya}")
    return str(dosya)

if __name__ == "__main__":
    generate_pdf()
