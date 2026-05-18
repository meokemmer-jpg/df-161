
# K16: Concurrent-Spawn-Mutex (fcntl-based, Trinity-CONSERVATIVE 2026-05-17)
def k16_lock_or_exit(df_name: str):
    """Acquire exclusive lock or exit(3). Prevents concurrent DF runs."""
    import fcntl, os, sys
    lock_path = f"/tmp/df-trinity-{df_name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd
    except BlockingIOError:
        sys.exit(3)


# K13: External-Anchor-Mock-RFC3161 (Trinity-CONSERVATIVE 2026-05-17)
def k13_anchor(payload_hash: str) -> dict:
    """Mock RFC3161-style timestamp anchor."""
    from datetime import datetime, timezone
    return {
        "anchor_type": "rfc3161-mock",
        "iso_ts": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
    }


# K12: HMAC-SHA256-Provenance (Trinity-CONSERVATIVE 2026-05-17)
def k12_provenance(payload: bytes, key: bytes = b"df-trinity-conservative-v1") -> dict:
    """Returns payload_hash + HMAC-SHA256 signature."""
    import hashlib, hmac
    return {
        "payload_hash": hashlib.sha256(payload).hexdigest(),
        "hmac_sha256": hmac.new(key, payload, hashlib.sha256).hexdigest(),
    }

"""OPS-Document-Freshness tracker DF-161."""

import re
import os
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime, timezone

DF_DIR = Path(__file__).parent
LOCK_DIR = Path("/tmp/df-161.lock")
DF_ID = "161"
DECISION_KEYWORDS_REGEX = re.compile(
    r"\b(entscheid[a-z]*|empfehl(?:e|en|t|st)|sollt(?:e|en|est)|recommend[a-z]*|decid[a-z]*|advis[a-z]*|propos[a-z]*)\b",
    re.IGNORECASE,
)


@dataclass
class TrackerOutput:
    welle: str = "25"
    df: str = "DF-161"
    iso_timestamp: str = ""
    source: str = "mock"
    documents_total: int = 0
    documents_stale_30d: int = 0
    documents_stale_90d: int = 0
    oldest_document: str = ""
    fresh_documents_pct: float = 0


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _file_stable(path, min_age_sec=300) -> bool:
    try:
        p = Path(path)
        if not p.is_file():
            return False
        return (time.time() - p.stat().st_mtime) >= min_age_sec
    except OSError:
        return False


def acquire_lock_with_identity() -> bool:
    stale_after_sec = 6 * 60 * 60
    now = time.time()

    try:
        LOCK_DIR.mkdir(mode=0o700)
        identity = {
            "df": "DF-161",
            "pid": os.getpid(),
            "created_at": iso_now(),
            "cwd": str(Path.cwd()),
        }
        (LOCK_DIR / "identity.json").write_text(
            json.dumps(identity, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return True
    except FileExistsError:
        try:
            age = now - LOCK_DIR.stat().st_mtime
        except OSError:
            return False

        if age <= stale_after_sec:
            return False

        try:
            for child in LOCK_DIR.iterdir():
                if child.is_file() or child.is_symlink():
                    child.unlink()
            LOCK_DIR.rmdir()
        except OSError:
            return False

        try:
            LOCK_DIR.mkdir(mode=0o700)
            identity = {
                "df": "DF-161",
                "pid": os.getpid(),
                "created_at": iso_now(),
                "cwd": str(Path.cwd()),
                "stale_lock_cleaned": True,
            }
            (LOCK_DIR / "identity.json").write_text(
                json.dumps(identity, ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            return True
        except OSError:
            return False
    except OSError:
        return False


def release_lock() -> None:
    try:
        for child in LOCK_DIR.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink()
        LOCK_DIR.rmdir()
    except FileNotFoundError:
        return
    except OSError:
        return


def k17_pre_action_verification(anchors) -> dict:
    """K17 Pre-Action-Verification (Welle-27-Fix: Path.exists() check)."""
    env_tag = os.environ.get("DF_ENV_TAG", "dev")
    missing = [str(a) for a in anchors if not Path(str(a)).exists()]
    return {"ok": len(missing) == 0, "missing_anchors": missing, "env_tag": env_tag}


def _is_real_api_enabled() -> bool:
    raw = os.environ.get("DF_161_REAL_API_ENABLED", "false")
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def scan_output_for_decision_keywords(text) -> list:
    if text is None:
        return []
    return sorted({m.group(0) for m in DECISION_KEYWORDS_REGEX.finditer(str(text))})


def assert_no_decision_keywords(output) -> None:
    if isinstance(output, str):
        text = output
    else:
        text = json.dumps(output, ensure_ascii=True, sort_keys=True)
    matches = scan_output_for_decision_keywords(text)
    if matches:
        raise ValueError("Q_0/K_0 violation: decision keywords found: " + ", ".join(matches))


def _parse_document_timestamp(path: Path):
    try:
        stat = path.stat()
        return datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    except OSError:
        return None


def _collect_from_directory(root: Path) -> TrackerOutput:
    now = datetime.now(timezone.utc)
    files = []
    for path in root.rglob("*"):
        if path.is_file() and _file_stable(path):
            ts = _parse_document_timestamp(path)
            if ts is not None:
                files.append((path, ts))

    total = len(files)
    stale_30 = 0
    stale_90 = 0
    oldest_path = ""
    oldest_ts = None

    for path, ts in files:
        age_days = (now - ts).total_seconds() / 86400
        if age_days > 30:
            stale_30 += 1
        if age_days > 90:
            stale_90 += 1
        if oldest_ts is None or ts < oldest_ts:
            oldest_ts = ts
            oldest_path = str(path)

    fresh_pct = 0
    if total:
        fresh_pct = round(((total - stale_30) / total) * 100, 2)

    return TrackerOutput(
        iso_timestamp=iso_now(),
        source="filesystem",
        documents_total=total,
        documents_stale_30d=stale_30,
        documents_stale_90d=stale_90,
        oldest_document=oldest_path,
        fresh_documents_pct=fresh_pct,
    )


def collect_tracker_output() -> TrackerOutput:
    if not _is_real_api_enabled():
        return TrackerOutput(iso_timestamp=iso_now(), source="mock")

    root_raw = os.environ.get("DF_161_DOCUMENT_ROOT", "").strip()
    if not root_raw:
        return TrackerOutput(iso_timestamp=iso_now(), source="mock")

    root = Path(root_raw)
    if not root.exists() or not root.is_dir():
        return TrackerOutput(iso_timestamp=iso_now(), source="mock")

    return _collect_from_directory(root)


def main() -> int:
    if not acquire_lock_with_identity():
        return 3

    try:
        pav = k17_pre_action_verification(
            ["DF-161", "OPS-Document-Freshness", "Stale-Document-Detection"]
        )
        if not pav.get("ok"):
            return 3

        output = collect_tracker_output()
        report = asdict(output)
        report["k17_pre_action_verification"] = pav

        assert_no_decision_keywords(report)

        reports_dir = DF_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_path = reports_dir / f"df-161-{date_tag}.json"
        report_path.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return 0
    except Exception as exc:
        sys.stderr.write(str(exc) + "\n")
        return 3
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())