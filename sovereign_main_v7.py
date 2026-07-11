#!/usr/bin/env python3
"""
sovereign_main_v7.py — Orkestrasyon Katmani
ZachXBT altı-aşamalı metodolojisinin otomatik karşılığı.
Her aşama arasında "aktif sürtünme" (insan onay noktası) bulunur.
"""

import sys
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))


class Stage(Enum):
    TRIGGER_DETECTION = "tetikleyici_tespiti"
    CLUSTERING = "kumeleme"
    OSINT_CORRELATION = "osint_korelasyonu"
    PROBABILITY_LANGUAGE = "olasilik_dili"
    DUAL_CHANNEL_PUBLISH = "cift_kanalli_yayin"


@dataclass
class CaseContext:
    case_id: str
    seed_address: str
    chain: str = "BTC"
    domain: str = None
    ip: str = None
    username: str = None
    stage_results: dict = field(default_factory=dict)
    human_approved: dict = field(default_factory=dict)


class ActiveFriction:
    @staticmethod
    def require_review(ctx: CaseContext, stage: Stage, summary: str) -> bool:
        print(f"\n--- [{stage.value}] Onay Bekliyor ---")
        print(summary)
        answer = input("Devam edilsin mi? (e/h): ").strip().lower()
        approved = answer == "e"
        ctx.human_approved[stage.value] = approved
        return approved


def stage_1_trigger_detection(ctx: CaseContext) -> dict:
    """
    blockscout_forensics.risk_v2 ile risk skoru hesaplar,
    deep_dormant_analysis ile dormant/uyanış paternini loglar (yan bilgi),
    randstorm_riski ile RNG zafiyeti riskini ekler.
    """
    from blockscout_forensics import risk_v2
    from deep_dormant import deep_dormant_analysis
    from sovereign_randstorm_scorer import randstorm_riski

    result = risk_v2(ctx.seed_address, chain=ctx.chain)
    if "error" in result:
        raise RuntimeError(f"risk_v2 hatası: {result['error']}")

    if ctx.chain == "BTC":
        deep_dormant_analysis(ctx.seed_address)

    randstorm = randstorm_riski(ctx.seed_address, chain=ctx.chain)
    result["randstorm"] = randstorm
    if randstorm.get("randstorm_donemi_icinde"):
        result["risk_skoru"] = min(100, result.get("risk_skoru", 0) + randstorm["risk_katkisi"])

    return result


def stage_2_clustering(ctx: CaseContext) -> dict:
    """
    Ortak-girdi kümeleme (common-input-ownership heuristic):
    Bir işlemde birden fazla input adresi varsa, aynı cüzdana/aktöre
    ait kabul edilir. Standart forensics yöntemi.
    """
    import requests

    if ctx.chain != "BTC":
        raise NotImplementedError("Kümeleme şu an sadece BTC için destekleniyor")

    address = ctx.seed_address
    try:
        r = requests.get(
            f"https://blockstream.info/api/address/{address}/txs",
            timeout=10
        )
        txs = r.json()
    except Exception as e:
        raise RuntimeError(f"Kümeleme için işlem verisi çekilemedi: {e}")

    cluster = set()
    multi_input_tx_count = 0

    for t in txs[:20]:
        inputs = [
            inp.get("prevout", {}).get("scriptpubkey_address", "")
            for inp in t.get("vin", [])
        ]
        inputs = [a for a in inputs if a]
        if len(inputs) > 1:
            multi_input_tx_count += 1
            cluster.update(inputs)

    cluster.discard(address)

    return {
        "seed_address": address,
        "cluster_size": len(cluster),
        "clustered_addresses": sorted(cluster)[:50],
        "multi_input_tx_count": multi_input_tx_count,
        "scanned_tx_count": len(txs[:20]),
    }


def stage_3_osint_correlation(ctx: CaseContext) -> dict:
    """
    Adresin bilinen bir domain/IP/username bağlamı varsa OSINT çalıştırır.
    Adresin kendisi domain/IP/username OLMADIĞI için bu alanlar opsiyoneldir;
    hiçbiri sağlanmamışsa boş ama geçerli bir sonuç döner (hata değil).
    """
    from osint_module import run_whois, run_dns, run_subdomain, run_shodan, run_sherlock

    result = {"context_provided": False}

    if ctx.domain:
        result["context_provided"] = True
        result["whois"] = run_whois(ctx.domain)
        result["dns"] = run_dns(ctx.domain)
        result["subdomains"] = run_subdomain(ctx.domain)

    if ctx.ip:
        result["context_provided"] = True
        result["shodan"] = run_shodan(ctx.ip)

    if ctx.username:
        result["context_provided"] = True
        result["sherlock"] = run_sherlock(ctx.username)

    if not result["context_provided"]:
        result["note"] = "domain/ip/username sağlanmadı, OSINT atlandı"

    return result


def stage_4_probability_language(ctx: CaseContext) -> dict:
    """
    Stage 1'in ham risk skorunu kalibre eder ve kesin yargı yerine
    olasılık diline çevirir (ZachXBT tarzı temkinli ifade).
    """
    from risk_calibration import kalibrasyon_skoru

    stage1 = ctx.stage_results.get(Stage.TRIGGER_DETECTION.value, {})
    ham_skor = stage1.get("risk_skoru", 0)

    kalibre = kalibrasyon_skoru(ctx.seed_address, ham_skor)
    skor = kalibre["kalibre_skor"]

    if skor >= 80:
        ifade = "bu adresin yüksek olasılıkla riskli/kötüye kullanım paternleri gösterdiği değerlendirilmektedir"
    elif skor >= 60:
        ifade = "bu adresin riskli davranış paternleriyle tutarlı olduğu görülmektedir, ancak kesin bir sonuç değildir"
    elif skor >= 30:
        ifade = "bazı dikkat çekici paternler mevcuttur, ancak bunlar kesin bir suç unsuru göstermez"
    else:
        ifade = "mevcut veriler önemli bir risk göstergesi sunmamaktadır"

    return {
        "ham_skor": ham_skor,
        "kalibre_skor": skor,
        "etiket": kalibre["etiket"],
        "kalibrasyon_aciklama": kalibre["aciklama"],
        "olasilik_ifadesi": ifade,
    }


def stage_5_dual_channel_publish(ctx: CaseContext) -> dict:
    """
    Tüm aşama sonuçlarını JSON'a yazar, ardından iki kanaldan yayınlar:
    1) PDF (pdf_report.generate_pdf)
    2) Kısa metin/markdown özeti (master_report.ozetle + markdown_yaz)
    """
    import json
    from pathlib import Path
    from datetime import datetime, timezone

    output_dir = Path.home() / "FORENSICS"
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"vaka_{ctx.case_id}_{ts}.json"

    full_report = {
        "case_id": ctx.case_id,
        "seed_address": ctx.seed_address,
        "chain": ctx.chain,
        "stages": ctx.stage_results,
    }
    with open(json_path, "w") as f:
        json.dump(full_report, f, indent=2, default=str, ensure_ascii=False)

    kanal_sonuclari = {"json_path": str(json_path)}

    try:
        from pdf_report import generate_pdf
        pdf_result = generate_pdf(str(json_path))
        kanal_sonuclari["pdf"] = pdf_result if pdf_result else "olusturuldu"
    except Exception as e:
        kanal_sonuclari["pdf_hata"] = str(e)

    try:
        from master_report import load_all_reports, ozetle, markdown_yaz
        raporlar = load_all_reports()
        ozet = ozetle(raporlar)
        md_path = output_dir / f"ozet_{ctx.case_id}_{ts}.md"
        markdown_yaz(ozet, str(md_path))
        kanal_sonuclari["markdown_path"] = str(md_path)
    except Exception as e:
        kanal_sonuclari["markdown_hata"] = str(e)

    return kanal_sonuclari


STAGE_FUNCTIONS = {
    Stage.TRIGGER_DETECTION: stage_1_trigger_detection,
    Stage.CLUSTERING: stage_2_clustering,
    Stage.OSINT_CORRELATION: stage_3_osint_correlation,
    Stage.PROBABILITY_LANGUAGE: stage_4_probability_language,
    Stage.DUAL_CHANNEL_PUBLISH: stage_5_dual_channel_publish,
}


def run_pipeline(case_id: str, seed_address: str, chain: str = "BTC") -> CaseContext:
    ctx = CaseContext(case_id=case_id, seed_address=seed_address, chain=chain)

    for stage in Stage:
        func = STAGE_FUNCTIONS[stage]
        try:
            result = func(ctx)
            ctx.stage_results[stage.value] = result
        except NotImplementedError as e:
            print(f"[ATLA] {stage.value}: {e}")
            continue
        except RuntimeError as e:
            print(f"[HATA] {stage.value}: {e}")
            break

        summary = f"{stage.value} tamamlandı. Anahtarlar: {list(result.keys()) if isinstance(result, dict) else result}"
        if not ActiveFriction.require_review(ctx, stage, summary):
            print(f"[DURDU] Kullanıcı {stage.value} aşamasında durdurdu.")
            break

    return ctx


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Kullanım: python3 sovereign_main_v7.py <case_id> <seed_address> [chain]")
        sys.exit(1)
    case_id = sys.argv[1]
    seed_address = sys.argv[2]
    chain = sys.argv[3] if len(sys.argv) > 3 else "BTC"
    run_pipeline(case_id, seed_address, chain)
