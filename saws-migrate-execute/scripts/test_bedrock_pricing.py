# test_bedrock_pricing.py
import bedrock_pricing as bp

def test_parse_price_dimensions_extracts_per_1k_token_rates():
    # Pure parser over a Pricing API PriceList JSON fragment.
    fragment = {
        "terms": {"OnDemand": {"x": {"priceDimensions": {
            "d1": {"unit": "1K tokens", "pricePerUnit": {"USD": "0.003"},
                   "description": "Input tokens for Claude"},
            "d2": {"unit": "1K tokens", "pricePerUnit": {"USD": "0.015"},
                   "description": "Output tokens for Claude"},
        }}}}}
    out = bp.parse_price_dimensions(fragment)
    assert out["input_per_1k_usd"] == 0.003
    assert out["output_per_1k_usd"] == 0.015

def test_unavailable_returns_banner_not_exception():
    out = bp.unavailable("network error")
    assert out["available"] is False
    assert "network error" in out["note"]

def test_static_fallback_returns_known_model():
    out = bp._static_fallback("us.anthropic.claude-haiku-4-5-20251001-v1:0")
    assert out is not None
    assert out["available"] is True
    assert out["input_per_1k_usd"] == 0.001
    assert out["output_per_1k_usd"] == 0.005
    assert "static fallback" in out["note"]

def test_static_fallback_partial_match():
    # us.anthropic.claude-sonnet-4-6 (no version suffix) should match
    out = bp._static_fallback("us.anthropic.claude-sonnet-4-6")
    assert out is not None
    assert out["available"] is True
    assert out["input_per_1k_usd"] == 0.003

def test_static_fallback_unknown_returns_none():
    out = bp._static_fallback("totally.fake.model-id")
    assert out is None
