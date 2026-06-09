# bedrock_pricing.py
"""Look up Amazon Bedrock on-demand token prices from the live AWS Pricing API.

Usage: python bedrock_pricing.py --region <r> --models <id,id,...>
Prints JSON {model_id: {input_per_1k_usd, output_per_1k_usd, available, note}}.
Never raises on lookup failure — emits an 'available: false' banner instead.
"""
import argparse, json, sys


def parse_price_dimensions(price_item: dict) -> dict:
    """Pure: pull input/output per-1K-token USD rates from one PriceList item."""
    inp = out = None
    terms = price_item.get("terms", {}).get("OnDemand", {})
    for term in terms.values():
        for dim in term.get("priceDimensions", {}).values():
            usd = float(dim.get("pricePerUnit", {}).get("USD", "0") or 0)
            desc = dim.get("description", "").lower()
            if "input" in desc:
                inp = usd
            elif "output" in desc:
                out = usd
    return {"input_per_1k_usd": inp, "output_per_1k_usd": out}


# Static fallback table: per-1K-token USD rates from public pricing pages.
# Used when the PriceList API doesn't return data (e.g. new cross-region inference profile IDs).
# Source: https://aws.amazon.com/bedrock/pricing/ (checked 2026-06)
STATIC_FALLBACK = {
    "anthropic.claude-haiku-4-5-20251001-v1:0":     {"input_per_1k_usd": 0.001, "output_per_1k_usd": 0.005},
    "us.anthropic.claude-haiku-4-5-20251001-v1:0":  {"input_per_1k_usd": 0.001, "output_per_1k_usd": 0.005},
    "anthropic.claude-sonnet-4-6-20250514-v1:0":    {"input_per_1k_usd": 0.003, "output_per_1k_usd": 0.015},
    "us.anthropic.claude-sonnet-4-6-20250514-v1:0": {"input_per_1k_usd": 0.003, "output_per_1k_usd": 0.015},
    "us.anthropic.claude-sonnet-4-6":               {"input_per_1k_usd": 0.003, "output_per_1k_usd": 0.015},
    "anthropic.claude-opus-4-8-20250610-v1:0":      {"input_per_1k_usd": 0.015, "output_per_1k_usd": 0.075},
    "us.anthropic.claude-opus-4-8-20250610-v1:0":   {"input_per_1k_usd": 0.015, "output_per_1k_usd": 0.075},
    "amazon.nova-micro-v1:0":                       {"input_per_1k_usd": 0.000035, "output_per_1k_usd": 0.00014},
    "amazon.nova-lite-v1:0":                        {"input_per_1k_usd": 0.00006, "output_per_1k_usd": 0.00024},
    "amazon.nova-pro-v1:0":                         {"input_per_1k_usd": 0.0008, "output_per_1k_usd": 0.0032},
}


def unavailable(note: str) -> dict:
    return {"available": False, "input_per_1k_usd": None,
            "output_per_1k_usd": None, "note": f"Pricing unavailable: {note}"}


def _static_fallback(model_id: str) -> dict | None:
    """Try the static fallback table. Returns a result dict or None."""
    entry = STATIC_FALLBACK.get(model_id)
    if entry:
        return {**entry, "available": True, "note": "static fallback (PriceList API had no entry)"}
    # Try stripping the version suffix for a partial match (e.g. us.anthropic.claude-sonnet-4-6)
    base = model_id.rsplit("-v", 1)[0] if "-v" in model_id else model_id
    for key, val in STATIC_FALLBACK.items():
        if key.startswith(base):
            return {**val, "available": True, "note": f"static fallback (matched {key})"}
    return None


def lookup(region: str, model_id: str) -> dict:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    try:
        # Pricing API is only served from us-east-1 / ap-south-1.
        client = boto3.client("pricing", region_name="us-east-1")
        resp = client.get_products(
            ServiceCode="AmazonBedrock",
            Filters=[{"Type": "TERM_MATCH", "Field": "model", "Value": model_id}],
            MaxResults=1,
        )
        items = resp.get("PriceList", [])
        if not items:
            # PriceList has no entry — try static fallback before giving up.
            fb = _static_fallback(model_id)
            if fb:
                return fb
            return unavailable(f"no PriceList entry for {model_id}")
        parsed = parse_price_dimensions(json.loads(items[0]))
        parsed["available"] = parsed["input_per_1k_usd"] is not None
        parsed["note"] = "" if parsed["available"] else "rates not found in price item"
        return parsed
    except (BotoCoreError, ClientError, ValueError) as e:
        # API call failed — still try static fallback.
        fb = _static_fallback(model_id)
        if fb:
            fb["note"] += f" (API error: {e})"
            return fb
        return unavailable(str(e))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--models", required=True)
    args = ap.parse_args(argv)
    out = {m.strip(): lookup(args.region, m.strip())
           for m in args.models.split(",") if m.strip()}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
