import json
import re
import urllib.request
from datetime import datetime

URLS = [
    "https://plinul.ro/benzinarii/floresti-cluj",
    "https://peko.ro/benzinarii/cj/cluj-napoca/mol-cluj-napoca-5-calea-turzii",
]

FALLBACK = {
    "mol":  {"price95": 8.57, "price100": 9.30},
    "romp": {"price95": 8.63, "price100": 9.12},
    "omv":  {"price95": 8.57, "price100": 9.30},
}

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")

def parse_plinul(html):
    """Parse plinul.ro/benzinarii/floresti-cluj table rows."""
    results = {}
    # Look for price patterns near station names
    # MOL on Avram Iancu
    mol = re.search(r'MOL.*?Avram Iancu.*?BENZINA EVO 95.*?([\d]+[.,][\d]+)\s*lei', html, re.DOTALL | re.IGNORECASE)
    romp = re.search(r'Rompetrol.*?DN1.*?Efix Benzina 95.*?([\d]+[.,][\d]+)\s*lei', html, re.DOTALL | re.IGNORECASE)
    omv = re.search(r'OMV.*?Luna de Sus.*?MaxxMotion 95.*?([\d]+[.,][\d]+)\s*lei', html, re.DOTALL | re.IGNORECASE)

    if mol:
        results["mol"] = float(mol.group(1).replace(",", "."))
    if romp:
        results["romp"] = float(romp.group(1).replace(",", "."))
    if omv:
        results["omv"] = float(omv.group(1).replace(",", "."))

    # Fallback: grab all prices from table rows with network names
    if not results:
        rows = re.findall(r'(MOL|Rompetrol|OMV).*?([\d]{1}[.,][\d]{2})\s*lei.*?(\d{1,2}\s*\w+\s*\d{4})', html, re.DOTALL | re.IGNORECASE)
        for row in rows:
            net = row[0].lower()
            price = float(row[1].replace(",", "."))
            if "rompetrol" in net and "romp" not in results:
                results["romp"] = price
            elif "mol" in net and "mol" not in results:
                results["mol"] = price
            elif "omv" in net and "omv" not in results:
                results["omv"] = price

    return results

def parse_peko_mol(html):
    """Parse peko.ro for MOL price as secondary source."""
    m = re.search(r'BENZINA EVO 95.*?(\d+[.,]\d+)\s*Lei', html, re.DOTALL | re.IGNORECASE)
    if m:
        return float(m.group(1).replace(",", "."))
    return None

def main():
    now = datetime.now()
    output = {
        "updated": now.strftime("%d %b %Y, %H:%M"),
        "updated_iso": now.isoformat(),
        "mol":  {**FALLBACK["mol"],  "source": "fallback"},
        "romp": {**FALLBACK["romp"], "source": "fallback"},
        "omv":  {**FALLBACK["omv"],  "source": "fallback"},
    }

    # Try plinul.ro first
    try:
        html = fetch("https://plinul.ro/benzinarii/floresti-cluj")
        parsed = parse_plinul(html)
        print(f"plinul.ro parsed: {parsed}")
        for station in ["mol", "romp", "omv"]:
            if station in parsed and 6.0 < parsed[station] < 15.0:
                output[station]["price95"] = parsed[station]
                output[station]["source"] = "plinul.ro"
    except Exception as e:
        print(f"plinul.ro failed: {e}")

    # Try peko.ro for MOL as backup
    if output["mol"]["source"] == "fallback":
        try:
            html2 = fetch("https://peko.ro/benzinarii/cj/cluj-napoca/mol-cluj-napoca-5-calea-turzii")
            mol_price = parse_peko_mol(html2)
            if mol_price and 6.0 < mol_price < 15.0:
                output["mol"]["price95"] = mol_price
                output["mol"]["source"] = "peko.ro"
                print(f"peko.ro MOL: {mol_price}")
        except Exception as e:
            print(f"peko.ro failed: {e}")

    # Determine cheapest
    prices = {s: output[s]["price95"] for s in ["mol", "romp", "omv"]}
    cheapest = min(prices, key=prices.get)
    output["cheapest"] = cheapest
    output["min_price"] = prices[cheapest]

    print(json.dumps(output, indent=2, ensure_ascii=False))

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("✅ prices.json written.")

if __name__ == "__main__":
    main()
