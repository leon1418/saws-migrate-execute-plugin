# test_preflight_bedrock.py
import json, subprocess, sys, pathlib
HERE = pathlib.Path(__file__).parent

def run(args, env=None):
    return subprocess.run([sys.executable, str(HERE / "preflight_bedrock.py"), *args],
                          capture_output=True, text=True, env=env)

def test_classify_access_denied_maps_to_authz_failure():
    # The pure classifier turns a botocore error code into a structured verdict.
    import preflight_bedrock as p
    v = p.classify_invoke_error("AccessDeniedException", "not authorized to perform bedrock:InvokeModel")
    assert v["ok"] is False
    assert v["reason"] == "authz"
    assert "bedrock:InvokeModel" in v["detail"]

def test_classify_model_not_available_suggests_cross_region_profile():
    import preflight_bedrock as p
    v = p.classify_invoke_error("ValidationException", "model identifier is invalid")
    assert v["ok"] is False
    assert v["reason"] == "model_unavailable"

def test_classify_throttle_is_ok_for_preflight():
    # A throttle on the 1-token probe means we ARE authorized — treat as pass.
    import preflight_bedrock as p
    v = p.classify_invoke_error("ThrottlingException", "rate exceeded")
    assert v["ok"] is True
