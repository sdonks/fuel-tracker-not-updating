import json
import re
import urllib.request
from datetime import datetime

# Preturile realiste incepand cu 2024 — orice sub MIN_PRICE e date vechi si se ignora
MIN_PRICE = 7.50
MAX_PRICE = 15.0

FALLBACK = {
    "mol":  {"price95": 8.57, "price100": 9.30},
    "romp": {"price95": 8.63, "price100": 9.12},
    "omv":  {"price95": 8.57, "price100": 9.30},
}

PEKO_URLS = {
    "mol":  "https://peko.ro/benzinarii/cj/cluj-napoca/mol-cluj-napoca-5-calea-turzii",
    "romp": "https://peko.ro/benzinarii/cj/cluj-napoca/rompetrol-cluj-5-vuia",
    "omv":  "https://peko.ro/benzinarii/cj/cluj-napoca/omv-manastur-omv-ro",
}

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")

def parse_peko_price(html):
    """
    Parse a peko.ro station page for benzina 95 and premium prices.
    Extracts all valid prices >= MIN_PRICE from the table, takes first two.
    """
    prices = re.findall(r'([\d]+[.,][\d]+)\s*Lei', html, re.IGNORECASE)
    valid = []
    for p in prices:
        val = float(p.replace(",", "."))
        if MIN_PRICE < val < MAX_PRICE:
            valid.append(val)

    price95  = valid[0] if len(valid) >= 1 else None
    price100 = valid[1] if len(valid) >= 2 else None
    return price95, price100

def parse_plinul_fallback(html):
    """
    Secondary: parse plinul.ro — only rows with dates from 2025/2026 and price >= MIN_PRICE.
    """
    results = {}
    rows = re.findall(
        r'(MOL|Rompetrol|OMV)[^\n]*?([\d]{1}[.,][\d]{2})\s*lei[^\n]*?(\d{2}\.\d{2}\.202[456])',
        html, re.IGNORECASE
    )
    for row in rows:
        net   = row[0].lower()
        price = float(row[1].replace(",", "."))
        if price < MIN_PRICE or price > MAX_PRICE:
            continue
        key = "romp" if "rompetrol" in net else "mol" if "mol" in net else "omv"
        if key not in results:
            results[key] = price
    return results

def main():
    now = datetime.now()
    output = {
        "updated":     now.strftime("%d %b %Y, %H:%M"),
        "updated_iso": now.isoformat(),
        "mol":  {**FALLBACK["mol"],  "source": "fallback"},
        "romp": {**FALLBACK["romp"], "source": "fallback"},
        "omv":  {**FALLBACK["omv"],  "source": "fallback"},
    }

    # --- Primary source: peko.ro (one page per station) ---
    for station, url in PEKO_URLS.items():
        try:
            html = fetch(url)
            p95, p100 = parse_peko_price(html)
            if p95:
                output[station]["price95"] = p95
                output[station]["source"]  = "peko.ro"
                if p100:
                    output[station]["price100"] = p100
                print(f"peko.ro {station}: {p95} / {p100}")
            else:
                print(f"peko.ro {station}: no valid price found")
        except Exception as e:
            print(f"peko.ro {station} failed: {e}")

    # --- Secondary source: plinul.ro (only for stations still on fallback) ---
    still_fallback = [s for s in ["mol","romp","omv"] if output[s]["source"] == "fallback"]
    if still_fallback:
        try:
            html2  = fetch("https://plinul.ro/benzinarii/floresti-cluj")
            parsed = parse_plinul_fallback(html2)
            for station in still_fallback:
                if station in parsed:
                    output[station]["price95"] = parsed[station]
                    output[station]["source"]  = "plinul.ro"
                    print(f"plinul.ro {station}: {parsed[station]}")
        except Exception as e:
            print(f"plinul.ro failed: {e}")

    # --- Determine cheapest ---
    prices   = {s: output[s]["price95"] for s in ["mol", "romp", "omv"]}
    cheapest = min(prices, key=prices.get)
    output["cheapest"]  = cheapest
    output["min_price"] = prices[cheapest]

    print(json.dumps(output, indent=2, ensure_ascii=False))

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("prices.json written.")

if __name__ == "__main__":
    main()
