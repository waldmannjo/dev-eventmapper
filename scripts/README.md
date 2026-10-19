# Scripts

## release.py

Computes the next version from Conventional Commits since the last `vX.Y.Z` tag
and writes `VERSION` plus a draft `CHANGELOG` entry into `app.py`. After the
release tag is pushed, `--publish` creates the GitHub release with the top
`CHANGELOG` entry as notes. Rules and
release steps: see the module docstring and `CLAUDE.md` → Releases.

```bash
python scripts/release.py              # dry run
python scripts/release.py --apply      # write app.py
python scripts/release.py --set 1.0.0  # explicit version
python scripts/release.py --publish    # GitHub release for the pushed tag
```


## validate_phase1.py

Validates Phase 1 (Quick Wins) improvements against a held-out validation set.

**Usage:**

```bash
export OPENAI_API_KEY="your-api-key"
python scripts/validate_phase1.py
```

**What it does:**

1. Loads historical data from `examples/CES_Umschlüsselungseinträge_all.xlsx`
2. Splits into 80% train / 20% validation (stratified by code)
3. Runs the improved mapping pipeline on validation set
4. Computes accuracy and detailed metrics
5. Saves results to `validation_results_phase1.csv`

**Success Criteria:**

- Overall accuracy improvement: >=10%
- High-confidence predictions: >=95% accuracy
- Cost reduction: ~40% (from dimension reduction)
