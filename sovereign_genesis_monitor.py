#!/usr/bin/env python3
"""
sovereign_genesis_monitor.py (v2)
-----------------------------
SovereignEngine module: dormancy monitoring and forensic reporting for
early-era ("Genesis period" / Patoshi-pattern) Bitcoin addresses.

SCOPE / ETHICAL BOUNDARY (per SovereignEngine project policy):
    - READ-ONLY. Queries public blockchain explorers for balance/tx data
      on addresses NOT owned by the operator.
    - Does NOT derive, brute-force, or store private keys for any
      monitored address.
    - Does NOT construct, sign, or broadcast transactions.
    - Purpose: dormancy tracking, movement alerting, and statistical/
      forensic reporting for research and case-study use.

v2 eklentileri: sovereign_randstorm_scorer'dan retry+fallback ve
ilk-işlem-tarihi tespiti yeniden kullanılıyor; hareket şiddeti
(TAM/KISMI/YOK) sınıflandırması; kalıcı JSONL geçmiş kaydı; opsiyonel
--age bayrağıyla uykuda kalma süresi hesaplama.

Usage:
    python3 sovereign_genesis_monitor.py --scan
    python3 sovereign_genesis_monitor.py --scan --age
    python3 sovereign_genesis_monitor.py --daemon --interval 3600
    python3 sovereign_genesis_monitor.py --report
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from sovereign_randstorm_scorer import _get_with_retry, _ilk_islem_tarihini_bul

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ADDRESS_LIST_FILE = os.path.join(BASE_DIR, "genesis_addresses.txt")
STATE_FILE = os.path.join(BASE_DIR, "genesis_monitor_state.json")
HISTORY_FILE = os.path.join(BASE_DIR, "genesis_monitor_history.jsonl")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

REQUEST_DELAY = 1.2  # seconds between calls — be polite to the public API

TELEGRAM_BOT_TOKEN = os.environ.get("SOVEREIGN_TG_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("SOVEREIGN_TG_CHAT_ID", "")

DEFAULT_SEED_ADDRESSES = [
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",  # Genesis block coinbase (block 0, protocol-unspendable)
]


# ---------------------------------------------------------------------------
# Address list handling
# ---------------------------------------------------------------------------

def load_address_list(path=ADDRESS_LIST_FILE):
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("# One Bitcoin address per line. Lines starting with # are ignored.\n")
            for addr in DEFAULT_SEED_ADDRESSES:
                f.write(addr + "\n")
    addresses = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                addresses.append(line)
    return addresses


# ---------------------------------------------------------------------------
# State handling (last-scan snapshot, for movement diffing)
# ---------------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


# ---------------------------------------------------------------------------
# History log (append-only, for time-series / trend analysis)
# ---------------------------------------------------------------------------

def log_history_entry(info):
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# On-chain data fetch (read-only, retry + mempool.space fallback)
# ---------------------------------------------------------------------------

def fetch_address_info(address, with_age=False):
    data = _get_with_retry(f"/address/{address}")
    if data is None:
        raise RuntimeError(f"{address} için API verisi alınamadı (blockstream.info + mempool.space başarısız)")

    chain = data.get("chain_stats", {})
    mempool = data.get("mempool_stats", {})
    funded = chain.get("funded_txo_sum", 0)
    spent = chain.get("spent_txo_sum", 0)
    tx_count = chain.get("tx_count", 0)
    spent_ratio = round(spent / funded, 4) if funded > 0 else 0.0

    info = {
        "address": address,
        "balance_sat": funded - spent,
        "funded_txo_sum": funded,
        "spent_txo_sum": spent,
        "tx_count": tx_count,
        "mempool_tx_count": mempool.get("tx_count", 0),
        "ever_spent": spent > 0,
        "spent_ratio": spent_ratio,
        "hareket_siddeti": (
            "TAM" if spent_ratio >= 0.95 else
            "KISMI" if spent_ratio > 0 else
            "YOK"
        ),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    if with_age:
        ilk_tarih = _ilk_islem_tarihini_bul(address, tx_count)
        if ilk_tarih:
            gecen_gun = (datetime.now(timezone.utc) - ilk_tarih).days
            info["ilk_islem_tarihi"] = ilk_tarih.isoformat()
            info["uykuda_gecen_yil"] = round(gecen_gun / 365.25, 1)
        else:
            info["ilk_islem_tarihi"] = None
            info["uykuda_gecen_yil"] = None

    return info


# ---------------------------------------------------------------------------
# HNDL / quantum-exposure scoring hook
# ---------------------------------------------------------------------------

def hndl_score(info):
    try:
        from hndl_risk_scorer import score_pubkey_exposure  # adjust to real signature
        return score_pubkey_exposure(pubkey_revealed=info["ever_spent"])
    except Exception:
        return "PUBKEY_EXPOSED" if info["ever_spent"] else "PUBKEY_HIDDEN"


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Telegram not configured (SOVEREIGN_TG_BOT_TOKEN / SOVEREIGN_TG_CHAT_ID) — skipping alert:")
        print("    " + message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        import requests
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
    except Exception as e:
        print(f"[!] Telegram alert failed: {e}")


# ---------------------------------------------------------------------------
# Core scan
# ---------------------------------------------------------------------------

def scan(addresses=None, verbose=True, with_age=False):
    addresses = addresses or load_address_list()
    state = load_state()
    results = []

    for addr in addresses:
        try:
            info = fetch_address_info(addr, with_age=with_age)
        except Exception as e:
            if verbose:
                print(f"[!] {addr}: fetch failed ({e})")
            time.sleep(REQUEST_DELAY)
            continue

        info["hndl_status"] = hndl_score(info)
        results.append(info)
        log_history_entry(info)

        prev = state.get(addr)
        if prev is not None and info["tx_count"] > prev.get("tx_count", 0):
            msg = (
                f"GENESIS MONITOR - hareket tespit edildi\n"
                f"Adres: {addr}\n"
                f"Onceki tx_count: {prev.get('tx_count', 0)} -> Yeni: {info['tx_count']}\n"
                f"Bakiye: {info['balance_sat']} sat\n"
                f"Hareket siddeti: {info['hareket_siddeti']}\n"
                f"Zaman: {info['checked_at']}"
            )
            send_telegram_alert(msg)
            if verbose:
                print(msg)

        state[addr] = info
        if verbose:
            yas = f", {info['uykuda_gecen_yil']} yil uykuda" if info.get("uykuda_gecen_yil") is not None else ""
            print(f"[{info['hareket_siddeti']}] {addr} - {info['balance_sat']} sat, tx_count={info['tx_count']}, hndl={info['hndl_status']}{yas}")

        time.sleep(REQUEST_DELAY)

    save_state(state)
    return results


# ---------------------------------------------------------------------------
# Reporting (fpdf2, consistent with pdf_report module conventions)
# ---------------------------------------------------------------------------

def generate_report(results, output_path=None):
    try:
        from fpdf import FPDF
    except ImportError:
        print("[!] fpdf2 not installed (`pip install fpdf2`) - skipping PDF, dumping JSON instead.")
        output_path = output_path or os.path.join(REPORT_DIR, f"genesis_report_{int(time.time())}.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        return output_path

    os.makedirs(REPORT_DIR, exist_ok=True)
    output_path = output_path or os.path.join(REPORT_DIR, f"genesis_report_{int(time.time())}.pdf")

    total_dormant = sum(1 for r in results if not r["ever_spent"])
    total_spent = len(results) - total_dormant
    total_balance = sum(r["balance_sat"] for r in results if not r["ever_spent"])

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "SovereignEngine - Genesis Dormancy Report", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Generated: {datetime.now(timezone.utc).isoformat()}", ln=True)
    pdf.cell(0, 8, f"Addresses monitored: {len(results)}", ln=True)
    pdf.cell(0, 8, f"Still dormant: {total_dormant}  |  Ever spent: {total_spent}", ln=True)
    pdf.cell(0, 8, f"Cumulative dormant balance: {total_balance} sat", ln=True)
    pdf.ln(5)

    pdf.set_font("Courier", "", 8)
    for r in results:
        yas = f" yil={r['uykuda_gecen_yil']}" if r.get("uykuda_gecen_yil") is not None else ""
        line = f"{r['address'][:20]:22} bal={r['balance_sat']:>14} tx={r['tx_count']:>4} {r['hareket_siddeti']:5}{yas} {r['hndl_status']}"
        pdf.cell(0, 5, line, ln=True)

    pdf.output(output_path)
    return output_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="SovereignEngine Genesis-era dormancy monitor (read-only)")
    parser.add_argument("--scan", action="store_true", help="Run a single scan pass")
    parser.add_argument("--daemon", action="store_true", help="Loop continuously")
    parser.add_argument("--interval", type=int, default=3600, help="Seconds between scans in daemon mode")
    parser.add_argument("--report", action="store_true", help="Generate a PDF/JSON report from the last scan state")
    parser.add_argument("--age", action="store_true", help="Also compute dormancy age (extra paginated API calls per address)")
    args = parser.parse_args()

    if args.report:
        state = load_state()
        if not state:
            print("[!] No state yet - run --scan first.")
            sys.exit(1)
        path = generate_report(list(state.values()))
        print(f"[+] Report written to {path}")
        return

    if args.daemon:
        print(f"[+] Daemon mode - scanning every {args.interval}s. Ctrl+C to stop.")
        while True:
            scan(with_age=args.age)
            time.sleep(args.interval)
    else:
        scan(with_age=args.age)


if __name__ == "__main__":
    main()
