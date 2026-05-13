# DF-161 OPS-Document-Freshness [CRUX-MK]

**Status:** SKELETON-CONDITIONAL (Welle-51 W51-B Skeleton-Wave-2)
**Domain:** OPS (Knowledge-Base-Hygiene, I_min)
**Welle:** 25

## Mission

Document-Freshness-Tracking. Tracking:
- Stale-Docs-Count
- Last-Edit-Age-Median-Days
- Critical-Docs-Aging-30d
- Orphan-Docs-Count

**NIEMALS Document-Delete oder Modify.**

## Usage

```bash
cd ~/Projects/dark-factories/df-161
python df-161-engine.py        # Mock-Mode default
pytest tests/                   # Existing tests
```

## Output

- Reports: `reports/df-161-{date}.json`
- STOP-Flag: `/tmp/df-161.stop`

[CRUX-MK]
