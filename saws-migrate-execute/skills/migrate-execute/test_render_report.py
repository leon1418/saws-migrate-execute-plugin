# test_render_report.py
import render_report as r

def test_summarize_extracts_headline_fields():
    payload = {"rewrite": {"branch_name": "bedrock-migration",
                           "files_changed": ["a.py", "b.py"]},
               "report": {"pass_rate": 0.91, "tests_passing": 8, "tests_total": 10,
                          "report_path": "/x/MIGRATION_REPORT_report.md"}}
    s = r.summarize(payload)
    assert "bedrock-migration" in s
    assert "91%" in s
    assert "8/10" in s
    assert "2 files" in s
