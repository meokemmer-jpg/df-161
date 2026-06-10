import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
# [CRUX-MK]
import importlib
from datetime import datetime, timedelta, timezone


_161 = importlib.import_module("161")
analyze_document_freshness = _161.analyze_document_freshness
write_report = _161.write_report


def test_analyze_document_freshness_and_write_report(tmp_path):
    now = datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)

    docs = {
        "README.md": 5,
        "guide.md": 40,
        "orphan/old.txt": 100,
        "critical/runbook.md": 31,
    }

    for rel_path, age_days in docs.items():
        path = tmp_path / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"content for {rel_path}", encoding="utf-8")
        ts = (now - timedelta(days=age_days)).timestamp()
        import os
        os.utime(path, (ts, ts))

    report = analyze_document_freshness(
        tmp_path,
        critical_docs=["critical/runbook.md"],
        now=now,
    )

    assert report["stale_docs_count"] == 3
    assert report["last_edit_age_median_days"] == 35.5
    assert report["critical_docs_aging_30d"] == 1
    assert report["orphan_docs_count"] == 1
    assert [doc["path"] for doc in report["documents"]] == [
        "README.md",
        "critical/runbook.md",
        "guide.md",
        "orphan/old.txt",
    ]

    output_path = tmp_path / "reports" / "df-161-2026-06-09.json"
    written = write_report(
        tmp_path,
        output_path,
        critical_docs=["critical/runbook.md"],
        now=now,
    )

    assert output_path.exists()
    assert written == report
