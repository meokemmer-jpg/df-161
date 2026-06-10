from __future__ import annotations

import json
import os
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DOC_EXTENSIONS = {
    ".md",
    ".rst",
    ".txt",
    ".adoc",
    ".org",
    ".markdown",
}


@dataclass(frozen=True)
class DocumentInfo:
    path: str
    last_edit_age_days: int
    is_orphan: bool
    is_critical: bool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iter_documents(root: Path, extensions: set[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            yield path


def _age_in_days(path: Path, now: datetime) -> int:
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return max(0, int((now - mtime).total_seconds() // 86400))


def analyze_document_freshness(
    root: str | os.PathLike[str],
    *,
    critical_docs: Iterable[str | os.PathLike[str]] = (),
    orphan_dirs: Iterable[str | os.PathLike[str]] = ("orphan", "orphans"),
    extensions: Iterable[str] = DOC_EXTENSIONS,
    now: datetime | None = None,
) -> dict:
    root_path = Path(root).resolve()
    now = now or _utc_now()
    ext_set = {ext.lower() for ext in extensions}
    orphan_dir_names = {Path(p).name for p in orphan_dirs}

    critical_set = {
        str((root_path / Path(p)).resolve()) if not Path(p).is_absolute() else str(Path(p).resolve())
        for p in critical_docs
    }

    documents: list[DocumentInfo] = []
    for doc in _iter_documents(root_path, ext_set):
        resolved = doc.resolve()
        relative_parts = resolved.relative_to(root_path).parts if resolved.is_relative_to(root_path) else ()
        is_orphan = any(part in orphan_dir_names for part in relative_parts[:-1])
        is_critical = str(resolved) in critical_set
        documents.append(
            DocumentInfo(
                path=str(resolved.relative_to(root_path)),
                last_edit_age_days=_age_in_days(resolved, now),
                is_orphan=is_orphan,
                is_critical=is_critical,
            )
        )

    ages = [doc.last_edit_age_days for doc in documents]
    critical_aged_30 = sum(1 for doc in documents if doc.is_critical and doc.last_edit_age_days > 30)

    report = {
        "generated_at": now.isoformat(),
        "root": str(root_path),
        "stale_docs_count": sum(1 for age in ages if age > 30),
        "last_edit_age_median_days": statistics.median(ages) if ages else 0,
        "critical_docs_aging_30d": critical_aged_30,
        "orphan_docs_count": sum(1 for doc in documents if doc.is_orphan),
        "documents": [doc.__dict__ for doc in sorted(documents, key=lambda d: d.path)],
    }
    return report


def write_report(
    root: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    *,
    critical_docs: Iterable[str | os.PathLike[str]] = (),
    orphan_dirs: Iterable[str | os.PathLike[str]] = ("orphan", "orphans"),
    extensions: Iterable[str] = DOC_EXTENSIONS,
    now: datetime | None = None,
) -> dict:
    report = analyze_document_freshness(
        root,
        critical_docs=critical_docs,
        orphan_dirs=orphan_dirs,
        extensions=extensions,
        now=now,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
# [CRUX-MK]
