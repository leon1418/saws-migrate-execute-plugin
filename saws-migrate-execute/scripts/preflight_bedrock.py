# preflight_bedrock.py
"""Bedrock fail-fast preflight: authorization, region/model availability, quota.

Usage: python preflight_bedrock.py --region <r> --models <id,id,...> [--cross-region]
Prints a JSON verdict to stdout; exit 0 if all models pass, 1 otherwise.
The 1-token InvokeModel probe costs a fraction of a cent (noted in output).
"""
import argparse, json, sys


def classify_invoke_error(code: str, message: str) -> dict:
    """Pure: map a botocore error code to a structured preflight verdict."""
    if code in ("AccessDeniedException",):
        return {"ok": False, "reason": "authz",
                "detail": f"Missing bedrock:InvokeModel — {message}"}
    if code in ("ValidationException", "ResourceNotFoundException"):
        return {"ok": False, "reason": "model_unavailable",
                "detail": f"Model not available in this region — {message}. "
                          f"Try a cross-region inference profile (e.g. us.<model-id>)."}
    if code in ("ThrottlingException", "ServiceQuotaExceededException"):
        # We got far enough to be throttled => we are authorized.
        return {"ok": True, "reason": "throttled_ok",
                "detail": "Authorized (probe throttled, which still proves access)."}
    return {"ok": False, "reason": "unknown", "detail": f"{code}: {message}"}


def probe_model(client, model_id: str) -> dict:
    """Real 1-token InvokeModel probe against a model id."""
    from botocore.exceptions import ClientError
    try:
        client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": "ping"}]}],
            inferenceConfig={"maxTokens": 1},
        )
        return {"ok": True, "reason": "ok", "detail": "InvokeModel authorized."}
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))
        return classify_invoke_error(code, msg)


def quota_rpm(region: str, model_id: str) -> int | None:
    """Best-effort on-demand requests-per-minute quota; None if unknown."""
    import boto3
    from botocore.exceptions import ClientError
    try:
        sq = boto3.client("service-quotas", region_name=region)
        # Bedrock quotas live under service code 'bedrock'; the exact quota
        # code varies per model. We scan for an InvokeModel RPM quota and
        # return the lowest applicable value, or None if not found.
        paginator = sq.get_paginator("list_service_quotas")
        lowest = None
        for page in paginator.paginate(ServiceCode="bedrock"):
            for q in page.get("Quotas", []):
                name = q.get("QuotaName", "").lower()
                if "invokemodel" in name.replace(" ", "") and "per minute" in name:
                    v = int(q.get("Value", 0))
                    lowest = v if lowest is None else min(lowest, v)
        return lowest
    except ClientError:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--models", required=True, help="comma-separated model ids")
    ap.add_argument("--dataset-size", type=int, default=0)
    args = ap.parse_args(argv)

    import boto3
    client = boto3.client("bedrock-runtime", region_name=args.region)
    results = []
    all_ok = True
    for model_id in [m.strip() for m in args.models.split(",") if m.strip()]:
        verdict = probe_model(client, model_id)
        rpm = quota_rpm(args.region, model_id)
        verdict["model_id"] = model_id
        verdict["rpm_quota"] = rpm
        if rpm is not None and args.dataset_size > rpm:
            verdict["quota_warning"] = (
                f"Dataset ({args.dataset_size}) exceeds ~{rpm} RPM quota — "
                f"Eval will pace with backoff and may be slow.")
        all_ok = all_ok and verdict["ok"]
        results.append(verdict)

    print(json.dumps({"ok": all_ok, "region": args.region,
                      "probe_cost_note": "1-token InvokeModel probe per model (~$0.00001 each)",
                      "models": results}, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
