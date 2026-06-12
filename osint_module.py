#!/usr/bin/env python3
"""Sovereign Engine - OSINT Modulu v1.0"""
import argparse, json, sys, os
from datetime import datetime
from pathlib import Path
import dns.resolver

dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
dns.resolver.default_resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

CONFIG = {
    "SHODAN_API_KEY": "YOUR_SHODAN_API_KEY",
    "OUTPUT_DIR": str(Path.home() / "FORENSICS"),
}

def run_whois(target):
    print(f"\n[WHOIS] {target}")
    try:
        import whois
        w = whois.whois(target)
        r = {"registrar": w.registrar, "org": w.org,
             "country": w.country, "emails": w.emails,
             "created": str(w.creation_date)}
        for k, v in r.items():
            print(f"  {k:12}: {v}")
        return r
    except Exception as e:
        print(f"  Hata: {e}")
        return {"error": str(e)}

def run_dns(domain):
    print(f"\n[DNS] {domain}")
    result = {}
    for rtype in ["A", "MX", "NS", "TXT"]:
        try:
            records = [str(r) for r in dns.resolver.resolve(domain, rtype, lifetime=5)]
            result[rtype] = records
            for r in records:
                print(f"  {rtype:6}: {r}")
        except Exception:
            pass
    return result

def run_subdomain(domain):
    print(f"\n[SUBDOMAIN] {domain}")
    subs = ["www","mail","api","dev","admin","ftp","vpn","app","cdn","portal"]
    found = []
    for s in subs:
        try:
            t = f"{s}.{domain}"
            ips = [str(r) for r in dns.resolver.resolve(t, "A", lifetime=3)]
            found.append({"sub": t, "ips": ips})
            print(f"  + {t} -> {ips}")
        except Exception:
            pass
    print(f"  Toplam: {len(found)}")
    return {"found": found, "count": len(found)}

def run_shodan(ip):
    print(f"\n[SHODAN] {ip}")
    if "YOUR_" in CONFIG["SHODAN_API_KEY"]:
        print("  API key yok, atlaniyor")
        return {"skipped": True}
    try:
        import shodan
        api = shodan.Shodan(CONFIG["SHODAN_API_KEY"])
        h = api.host(ip)
        r = {"org": h.get("org"), "ports": h.get("ports", []),
             "vulns": list(h.get("vulns", {}).keys()),
             "country": h.get("country_name")}
        print(f"  Org  : {r['org']}")
        print(f"  Ports: {r['ports']}")
        if r["vulns"]: print(f"  CVEs : {r['vulns']}")
        return r
    except Exception as e:
        print(f"  Hata: {e}")
        return {"error": str(e)}

def run_sherlock(username):
    print(f"\n[SHERLOCK] {username}")
    try:
        import subprocess
        r = subprocess.run(
            ["python3", "-m", "sherlock_project", username, "--print-found", "--no-color"],
            capture_output=True, text=True,
            cwd=str(Path.home() / "TOOLS" / "sherlock"), timeout=60
        )
        found = [l for l in r.stdout.split("\n") if l.startswith("[+]")]
        for l in found: print(f"  {l}")
        print(f"  Toplam: {len(found)}")
        return {"found": found, "count": len(found)}
    except Exception as e:
        print(f"  Hata: {e}")
        return {"error": str(e)}

def save_report(target, data):
    p = Path(CONFIG["OUTPUT_DIR"])
    p.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    f = p / f"osint_{target.replace('.','_')}_{ts}.json"
    with open(f, "w") as fp:
        json.dump(data, fp, indent=2, default=str)
    print(f"\n Rapor: {f}")
    return str(f)

def main():
    ap = argparse.ArgumentParser(description="Sovereign Engine OSINT")
    ap.add_argument("-t", "--target", help="Domain veya IP")
    ap.add_argument("-u", "--username", help="Kullanici adi")
    ap.add_argument("--shodan-key", help="Shodan API key")
    ap.add_argument("--no-subdomain", action="store_true")
    args = ap.parse_args()

    if not args.target and not args.username:
        ap.print_help(); sys.exit(1)

    if args.shodan_key:
        CONFIG["SHODAN_API_KEY"] = args.shodan_key

    print("=" * 50)
    print("  Sovereign Engine - OSINT v1.0")
    print(f"  {datetime.utcnow().isoformat()}Z")
    print("=" * 50)

    report = {"target": args.target, "username": args.username,
              "timestamp": datetime.utcnow().isoformat()+"Z", "results": {}}

    if args.target:
        t = args.target
        report["results"]["whois"] = run_whois(t)
        report["results"]["dns"] = run_dns(t)
        if not args.no_subdomain and not t.replace(".","").isdigit():
            report["results"]["subdomains"] = run_subdomain(t)
        try:
            ip = str(list(dns.resolver.resolve(t, "A", lifetime=3))[0])
            report["results"]["shodan"] = run_shodan(ip)
        except Exception:
            report["results"]["shodan"] = run_shodan(t)

    if args.username:
        report["results"]["sherlock"] = run_sherlock(args.username)

    save_report(args.target or args.username, report)

if __name__ == "__main__":
    main()
