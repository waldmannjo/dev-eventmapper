# Unknown Carrier Improvements

**Date:** 2026-02-25
**Status:** Draft / Ready for Prioritization
**Scope:** Improving mapping quality and efficiency for carriers not represented in the history file

---

## Problem Statement

The pipeline has two distinct operating modes:

| Mode | Condition | Accuracy | LLM load |
|------|-----------|----------|----------|
| Known carrier | Carrier text in history | ~97% (k-NN) | ~12% of rows |
| Unknown carrier | Carrier text not in history | ~87% (LLM only) | 100% of rows |

For unknown carriers, k-NN fires on 0 rows, the cross-encoder (CE) produces near-zero confidence scores (flat score distribution across candidates), and LLM ends up handling every row. This is slow and expensive, and the quality ceiling is bounded by LLM accuracy (~87%) rather than k-NN accuracy (~97%).

---

## Improvements

### 1. "Save to History" Button in the App

**Problem:** After a successful LLM run on an unknown carrier, the mappings are discarded. The next run of the same carrier starts from scratch.

**Fix:** Add a "Save to History" button to the Step 4 results UI. When clicked:
1. Filter rows where `source == "llm-batch"` and confidence is above a review threshold (e.g. ≥ 0.70)
2. Show the user a preview of rows to be saved (count + sample)
3. On confirmation, append `Description` + `AEB Event Code` columns to `CES_Umschlüsselungseinträge_all.xlsx`
4. Delete the embedding cache files so it rebuilds on next run

This creates a flywheel: unknown carrier → LLM → review → save → next run uses k-NN at 97%.

**Files:** `app.py` (new button + export logic), `backend/mapper.py` (no changes needed)
**Effort:** Low | **Impact:** High | **Dependencies:** None

---

### 2. Lower k-NN Threshold Option

**Problem:** `knn_threshold = 0.93` is strict. Carriers with similar (but not identical) text style to known carriers won't get k-NN matches.

**Fix:** Expose `knn_threshold` as a UI slider (range 0.80–0.99, default 0.93) so users can tune it per document. Add a note in the UI: "Lower threshold = more history matches, higher risk of wrong matches."

Alternatively, run a secondary k-NN sweep at a lower threshold (e.g. 0.85) with lower confidence, routing those to LLM for verification rather than accepting directly.

**Files:** `app.py` (slider), `backend/mapper.py` (no changes needed — already config-driven)
**Effort:** Low | **Impact:** Medium | **Dependencies:** None

---

### 3. Expand AEB Code Descriptions in `codes.py`

**Problem:** The CE and BM25 stages match carrier text against AEB code descriptions. For unknown carriers, the code descriptions don't contain the carrier's jargon, so the CE can't find a confident match.

**Fix:** Expand each AEB code entry in `codes.py` with additional carrier-style phrasings and synonyms — particularly English operational terms used by international carriers. Examples:

- `DEL` (Delivered): add "POD", "proof of delivery", "consignee signed", "delivered to recipient"
- `CAS` (Consignee Absent): add "not home", "recipient not available", "failed attempt", "nobody present"
- `ERR` (Error/Exception): add "exception", "failed delivery", "undeliverable", "problem with shipment"
- `HIN` (Hub In): add "arrived at facility", "inbound scan", "received at hub", "arrived at terminal"
- `WRN` (Warning): add "unable to collect", "pickup failed", "collection refused", "capacity exceeded"

This directly improves CE candidate quality and BM25 scoring without any model changes.

**Files:** `codes.py`
**Effort:** Low–Medium | **Impact:** Medium | **Dependencies:** None (requires cache rebuild after change)

---

### 4. Pass All 31 Codes to LLM for Unknown Carriers

**Problem:** The LLM fallback currently only sees the top-3 CE candidates. For unknown carriers the CE's ranking is unreliable — the correct code may not be in the top-3 at all.

**Fix:** When CE confidence is below a low threshold (e.g. < 0.20, meaning the CE has essentially no signal), pass all 31 AEB codes to the LLM instead of just the top-3. The LLM is capable of selecting from a full list and will produce better results than being forced to choose from a bad shortlist.

```python
if max_ce_conf < 0.20:
    # CE has no signal — give LLM the full code list
    candidates = [{"code": c[0], "desc": c[1], "score": 0.0} for c in CODES]
else:
    candidates = top_3_from_ce
```

**Files:** `backend/mapper.py` (`run_mapping_step4`, `classify_single_row`)
**Effort:** Low | **Impact:** Medium | **Dependencies:** None

---

### 5. Cross-Encoder Fine-Tuning on Domain Data

**Problem:** The CE model (`mmarco-mMiniLMv2-L12-H384-v1`) was trained on general multilingual retrieval. It has no exposure to logistics event terminology or the AEB code taxonomy.

**Fix:** Fine-tune the CE on confirmed historical mappings as (carrier_text, code_description, label) triplets. Positive pairs: correct mappings. Negative pairs: same carrier text paired with wrong codes (hard negatives from confused pairs in the confusion matrix — e.g. WRN vs CAS, INF vs OFD).

Training data is already available in `CES_Umschlüsselungseinträge_all.xlsx` (11k mappings). This would require a training script using `sentence-transformers` `CrossEncoderTrainer`.

**Files:** New `scripts/finetune_cross_encoder.py`
**Effort:** High | **Impact:** High | **Dependencies:** Labeled data (available), GPU recommended

---

## Priority Summary

| # | Improvement | Effort | Impact | Notes |
|---|-------------|--------|--------|-------|
| 1 | Save to History button | Low | High | Compounds over time — do first |
| 2 | Lower k-NN threshold slider | Low | Medium | Quick UI addition |
| 3 | Expand code descriptions | Low–Med | Medium | No model changes needed |
| 4 | Full code list to LLM | Low | Medium | Simple conditional in mapper |
| 5 | Fine-tune cross-encoder | High | High | Long-term, requires GPU |

## Recommended Sequence

1. **First:** Item 1 (Save to History) — turns every LLM run into training data
2. **Batch:** Items 2, 3, 4 — low-effort improvements that help immediately
3. **Later:** Item 5 — once enough domain-confirmed data has accumulated via Item 1
