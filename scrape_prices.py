import json
import re
import urllib.request
from datetime import datetime

# peko.ro afiseaza "X ore în urmă", "X zile în urmă", "X luni în urmă", "X ani în urmă"
# Acceptam doar preturi actualizate in ultimele 12 luni
MAX_AGE_DAYS = 365
MIN_PRICE    = 5.0
MAX_PRICE    = 15.0

FALLBACK = {
    "mol":  {"price95": 8.65, "price100": 9.38},
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

def age_to_days(age_str):
    """
    Converteste textul de actualizare de pe peko.ro in numar de zile.
    "5 ore in urma" -> 0, "3 zile in urma" -> 3,
    "2 luni in urma" -> 60, "1 an in urma" -> 365
    """
    s = age_str.lower().strip()
    if any(w in s for w in ["acum", "azi", "minut", "secund", "or"]):
        return 0
    m = re.search(r'(\d+)\s*(zi|zile|lun|luna|luni|an\b|ani)', s)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    if unit.startswith("zi"):
        return n
    if unit.startswith("lun"):
        return n * 30
    if unit.startswith("an"):
        return n * 365
    return None

def parse_peko_table(html):
    """
    Tabelul peko.ro (markdown rendered):
    | Benzina Standard | BENZINA EVO 95 | 8.65 Lei | 5 ore in urma |
    Filtreaza dupa coloana Actualizare — doar randuri mai noi de MAX_AGE_DAYS.
    """
    rows = re.findall(
        r'\|\s*([^|]+)\|\s*(\d+[.,]\d+)\s*Lei\s*\|\s*([^|\n]+)\|?',
        html, re.IGNORECASE
    )

    valid = []
    for product, price_str, age_str in rows:
        price = float(price_str.replace(",", "."))
        age   = age_to_days(age_str)
        print(f"  '{product.strip()}': {price} lei, varsta='{age_str.strip()}' -> {age} zile")
        if age is None or age > MAX_AGE_DAYS:
            print(f"    -> IGNORAT (prea vechi sau neparsabil)")
            continue
        if price < MIN_PRICE or price > MAX_PRICE:
            print(f"    -> IGNORAT (pret invalid)")
            continue
        valid.append(price)

    # primul = 95, al doilea = premium
    p95  = valid[0] if len(valid) >= 1 else None
    p100 = valid[1] if len(valid) >= 2 else None
    return p95, p100

def main():
    now = datetime.now()
    output = {
        "updated":     now.strftime("%d %b %Y, %H:%M"),
        "updated_iso": now.isoformat(),
        "mol":  {**FALLBACK["mol"],  "source": "fallback"},
        "romp": {**FALLBACK["romp"], "source": "fallback"},
        "omv":  {**FALLBACK["omv"],  "source": "fallback"},
    }

    for station, url in PEKO_URLS.items():
        print(f"\n--- {station.upper()} ---")
        try:
            html = fetch(url)
            p95, p100 = parse_peko_table(html)
            if p95:
                output[station]["price95"] = p95
                output[station]["source"]  = "peko.ro"
                if p100:
                    output[station]["price100"] = p100
                print(f"FINAL {station}: {p95} / {p100}")
            else:
                print(f"FINAL {station}: niciun pret valid -> fallback {FALLBACK[station]['price95']}")
        except Exception as e:
            print(f"EROARE {station}: {e}")

    prices   = {s: output[s]["price95"] for s in ["mol", "romp", "omv"]}
    cheapest = min(prices, key=prices.get)
    output["cheapest"]  = cheapest
    output["min_price"] = prices[cheapest]

    print("\n--- OUTPUT ---")
    print(json.dumps(output, indent=2, ensure_ascii=False))

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("prices.json scris.")

if __name__ == "__main__":
    main()
