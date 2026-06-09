# render_report.py
"""Summarize a completed Track 2 execute run for in-chat display.

summarize(payload) -> str is pure (testable). main() also copies the report
file to a stable ~/saws-migrate-results/ location.
"""
import json, sys, shutil, pathlib, argparse


def summarize(payload: dict) -> str:
    rw = payload.get("rewrite", {}) or {}
    rp = payload.get("report", {}) or {}
    pass_rate = rp.get("pass_rate", 0) or 0
    files = rw.get("files_changed", []) or []
    lines = [
        "AI Migration Complete!",
        f"- Branch: {rw.get('branch_name', '(none)')}",
        f"- Prompt eval pass rate: {round(pass_rate * 100)}%",
        f"- Files modified: {len(files)} files",
        f"- Tests: {rp.get('tests_passing', 0)}/{rp.get('tests_total', 0)} passing",
        f"- Report: {rp.get('report_path', '(unknown)')}",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("payload_json", help="path to the run-2 result JSON")
    ap.add_argument("--results-dir", default=str(pathlib.Path.home() / "saws-migrate-results"))
    args = ap.parse_args(argv)
    payload = json.loads(pathlib.Path(args.payload_json).read_text())
    report_path = (payload.get("report", {}) or {}).get("report_path")
    if report_path and pathlib.Path(report_path).exists():
        dest_dir = pathlib.Path(args.results_dir)
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report_path, dest_dir / pathlib.Path(report_path).name)
    print(summarize(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
