# Sentinel AI Feedback Loop — Testing Guide

**Purpose:** This guide walks you through three end-to-end scenarios that demonstrate the AI feedback loop working in a live Sentinel environment. Each scenario shows how analyst corrections teach the review agent to propose regulatory database updates, and how approving a recommendation changes future compliance decisions.

**Time required:** ~25 minutes for all three scenarios  
**Prerequisites:** Sentinel running (local or AWS), Insights Dashboard accessible at `/insights`

---

## How the Feedback Loop Works (Quick Recap)

```
1. Upload document → compliance result (APPROVED / REJECTED)
2. Analyst clicks 👎 → types a correction comment → submits
3. Navigate to Insights → Run Review Agent
4. Review agent (LLM) analyses corrections → proposes a recommendation
5. Admin approves recommendation → regulatory_db.json updated live
6. Re-upload same document → new result reflects the change
```

Two recommendation types:
- **`missing_rule`** — a required clause is absent from the database; add it so future documents are checked for it
- **`comprehension_failure`** — the clause exists in the DB but the LLM misread unusual phrasing; add a few-shot example so the LLM recognises it next time

---

## Test Documents (in `sample_docs/`)

| File | Doc Type | Scenario | Use |
|------|----------|----------|-----|
| `fl_test_s1_nda_all_current_clauses_APPROVED.txt` | LEGAL_CONTRACT | Scenario 1 | Upload first — triggers missing_rule feedback |
| `fl_test_s1_nda_with_breach_notice_APPROVED.txt` | LEGAL_CONTRACT | Scenario 1 | Upload after approval — verification (should still pass) |
| `fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt` | CREDIT_AGREEMENT | Scenario 2 | Upload first — LLM misses unusual phrasing → REJECTED |
| `fl_test_s3_employment_all_current_clauses_APPROVED.txt` | EMPLOYMENT_CONTRACT | Scenario 3 | Upload first — triggers missing_rule feedback |
| `fl_test_s3_employment_with_remote_work_APPROVED.txt` | EMPLOYMENT_CONTRACT | Scenario 3 | Upload after approval — verification (should pass) |

---

## Scenario 1 — Missing Rule: Data Breach Notification in NDAs

**Concept:** The regulatory database currently requires 3 clauses for `LEGAL_CONTRACT` documents (force majeure, limitation of liability, dispute resolution). An analyst notices that NDAs routinely omit data breach notification obligations — a real compliance gap. After the feedback cycle, the system adds this as a 4th required clause.

**Expected outcomes:**

| Step | Document | Result Before Fix | Result After Fix |
|------|----------|-------------------|------------------|
| Upload trigger doc | `fl_test_s1_nda_all_current_clauses_APPROVED.txt` | ✅ APPROVED | ❌ REJECTED (missing breach notice) |
| Upload verification doc | `fl_test_s1_nda_with_breach_notice_APPROVED.txt` | ✅ APPROVED | ✅ APPROVED |

---

### Step 1-A: Upload the trigger document

1. Open Sentinel in your browser
2. Click **Upload Document** and select:
   ```
   sample_docs/fl_test_s1_nda_all_current_clauses_APPROVED.txt
   ```
3. Wait for the analysis stream to complete
4. **Verify:** Result shows **APPROVED** — the NDA contains all 3 currently required clauses

---

### Step 1-B: Submit negative feedback

1. Click the **👎 thumbs-down** button below the result
2. In the comment box that appears, type **exactly**:
   ```
   NDA approved but missing a mandatory 48-hour data breach notification obligation — this clause should be required for all NDAs handling confidential data
   ```
3. Click **Submit Feedback**
4. **Verify:** Confirmation message appears. The correction is logged to `correction_examples.jsonl`

---

### Step 1-C: Run the review agent

1. Navigate to the **Insights Dashboard** (click "Insights" in the top navigation)
2. Confirm you see a **Negative Feedback** count ≥ 1 for `LEGAL_CONTRACT`
3. In the **Run Review Agent** section, select **Min evidence: 1** from the dropdown
4. Click **Run Review Agent**
5. Watch the SSE log stream. You should see lines similar to:
   ```
   [review] Analysing 1 correction(s) for doc_type=LEGAL_CONTRACT
   [review] Proposed: missing_rule — "data breach notification clause"
   [review] Recommendation saved (id=1)
   ```
6. **Verify:** The **Recommendations** table populates with a new row:
   - Type: `missing_rule`
   - Proposed clause: `data breach notification clause`
   - Status: `PENDING`

---

### Step 1-D: Approve the recommendation

1. In the Recommendations table, find the `data breach notification clause` row
2. Click **Approve**
3. **Verify:** Status changes to `APPROVED` and a green toast confirms the patch was applied
4. Check `backend/data/regulatory_db.json` — the `LEGAL_CONTRACT` entry should now include `"data breach notification clause"` in its required clauses list

---

### Step 1-E: Re-upload the trigger document (should now be REJECTED)

1. Upload `fl_test_s1_nda_all_current_clauses_APPROVED.txt` again
2. **Expected result:** ❌ **REJECTED** — the NDA is now missing the newly required data breach notification clause

---

### Step 1-F: Upload the verification document (should remain APPROVED)

1. Upload `fl_test_s1_nda_with_breach_notice_APPROVED.txt`
2. **Expected result:** ✅ **APPROVED** — this NDA includes Section 7 (Data Breach Notification Clause) which satisfies all 4 required clauses including the newly added one

---

### Step 1-G (Optional): Undo the recommendation

1. In the Recommendations table, find the approved row and click **Undo**
2. **Verify:** `data breach notification clause` is removed from `regulatory_db.json`
3. Re-upload the trigger document — it should be **APPROVED** again (reverting to pre-fix behaviour)

---

## Scenario 2 — Comprehension Failure: Unusual Clause Headings in Credit Agreements

**Concept:** A credit agreement contains all 4 required clauses (`governing law`, `events of default`, `indemnification`, `representations and warranties`) but uses non-standard headings that confuse the LLM. The document is rejected despite being compliant. After adding a few-shot correction example, the LLM learns to recognise the unusual phrasing.

**Key unusual headings in the test document:**
- "Obligor Acceleration Events" → means *events of default*
- "Mutual Hold-Harmless and Cost-Shifting Undertaking" → means *indemnification clause*

**Expected outcomes:**

| Step | Document | Result Before Fix | Result After Fix |
|------|----------|-------------------|------------------|
| Upload | `fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt` | ❌ REJECTED (LLM misses unusual headings) | ✅ APPROVED |

> **Note:** If your local LLM (Gemma 3:27b or similar) is powerful enough to resolve the unusual phrasing, the document may already pass. If that happens, this test demonstrates that the LLM is performing well — skip to Step 2-D to still practice the comprehension_failure recommendation flow by submitting a positive override instead and using a smaller model scenario.

---

### Step 2-A: Upload the credit agreement

1. Upload:
   ```
   sample_docs/fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt
   ```
2. Wait for the analysis to complete
3. **Expected result:** ❌ **REJECTED** — with missing clauses listed as `events of default clause` and/or `indemnification clause`
4. Review the clause results table and note which clauses the LLM marked as ABSENT

---

### Step 2-B: Submit a comprehension correction

1. Click **👎 thumbs-down**
2. In the comment box, type **exactly**:
   ```
   This credit agreement is compliant and should be APPROVED. Section 5 titled "Obligor Acceleration Events" IS the events of default clause — this is standard Northbridge drafting. Section 6 titled "Mutual Hold-Harmless and Cost-Shifting Undertaking" IS the indemnification clause. The LLM failed to recognise these non-standard headings.
   ```
3. Click **Submit Feedback**

---

### Step 2-C: Run the review agent

1. Go to Insights Dashboard
2. Click **Run Review Agent** (Min evidence: 1)
3. Watch the SSE log. Look for:
   ```
   [review] Proposed: comprehension_failure — "events of default clause"
   [review] Proposed: comprehension_failure — "indemnification clause"
   ```
4. **Verify:** Two new `comprehension_failure` recommendations appear in the table

---

### Step 2-D: Approve the comprehension failure recommendations

1. Click **Approve** on both comprehension failure rows
2. **Verify:** Each approval adds a new entry to `backend/data/few_shot_examples.jsonl` containing the document excerpt and the correct clause mapping

---

### Step 2-E: Re-upload the credit agreement (should now be APPROVED)

1. Upload `fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt` again
2. **Expected result:** ✅ **APPROVED** — the compliance agent's prompt now includes few-shot examples showing that "Obligor Acceleration Events" maps to events of default and "Mutual Hold-Harmless..." maps to indemnification

---

## Scenario 3 — Missing Rule: Remote Work Policy in Employment Contracts

**Concept:** Employment contracts currently require 4 clauses. An HR analyst notices that the system approves contracts that have no remote work / flexible working provisions — a gap in the company's standard requirements. After the feedback cycle, a remote work policy clause is added as a 5th required clause.

**Expected outcomes:**

| Step | Document | Result Before Fix | Result After Fix |
|------|----------|-------------------|------------------|
| Upload trigger doc | `fl_test_s3_employment_all_current_clauses_APPROVED.txt` | ✅ APPROVED | ❌ REJECTED (no remote work clause) |
| Upload verification doc | `fl_test_s3_employment_with_remote_work_APPROVED.txt` | ✅ APPROVED | ✅ APPROVED |

---

### Step 3-A: Upload the trigger employment contract

1. Upload:
   ```
   sample_docs/fl_test_s3_employment_all_current_clauses_APPROVED.txt
   ```
2. **Verify:** Result is ✅ **APPROVED** — all 4 current required clauses are present

---

### Step 3-B: Submit negative feedback

1. Click **👎**
2. Type **exactly**:
   ```
   Employment contract approved but missing a remote work and flexible arrangements policy — all employment contracts should explicitly address remote working eligibility, home office requirements, and equipment provision. This is now a standard requirement.
   ```
3. Click **Submit Feedback**

---

### Step 3-C: Run the review agent

1. Insights Dashboard → **Run Review Agent**
2. Watch for:
   ```
   [review] Proposed: missing_rule — "remote work and flexible arrangements policy"
   ```
3. **Verify:** New `missing_rule` recommendation appears for `EMPLOYMENT_CONTRACT`

---

### Step 3-D: Approve the recommendation

1. Click **Approve** on the remote work policy row
2. **Verify:** `regulatory_db.json` updated — `EMPLOYMENT_CONTRACT` now has 5 required clauses

---

### Step 3-E: Re-upload trigger contract (should now be REJECTED)

1. Upload `fl_test_s3_employment_all_current_clauses_APPROVED.txt` again
2. **Expected result:** ❌ **REJECTED** — missing remote work and flexible arrangements policy

---

### Step 3-F: Upload the verification contract (should remain APPROVED)

1. Upload `fl_test_s3_employment_with_remote_work_APPROVED.txt`
2. **Expected result:** ✅ **APPROVED** — Section 7 (Remote Work and Flexible Arrangements Policy) satisfies the new requirement

---

## Resetting the Environment

After completing all three scenarios, the regulatory database will have 2 extra clauses (data breach notification in LEGAL_CONTRACT and remote work policy in EMPLOYMENT_CONTRACT) and `few_shot_examples.jsonl` will have 2 new entries. To reset to the baseline state:

### Option A: Undo via the UI (recommended)
1. Go to Insights → Recommendations table
2. For each `APPROVED` recommendation, click **Undo**
3. This reverses both DB patches and removes few-shot entries

### Option B: Reset from git
```bash
cd /opt/sentinel/backend/data
git checkout HEAD -- regulatory_db.json
> few_shot_examples.jsonl    # truncate to empty
> correction_examples.jsonl  # truncate to empty
sudo systemctl restart sentinel
```

---

## Troubleshooting

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| Document classified as wrong type | LLM routing confidence low | Check routing_confidence in result; try re-uploading |
| Review agent produces no recommendations | Min evidence too high | Lower REVIEW_MIN_EVIDENCE env var to 1 |
| Recommendation not changing result after approve | Service cache / DB not refreshed | `POST /api/admin/regulatory-db/reload` or restart service |
| APPROVED when REJECTED expected after missing_rule fix | Few-shot examples overriding DB rule | Check few_shot_examples.jsonl for conflicting positive examples |
| SSE stream hangs | Ollama not responding | Check `GET /api/health`; verify Ollama is running |

---

## Summary of Expected Clause Counts After Each Approval

| Doc Type | Before Demo | After S1 Approve | After S3 Approve |
|----------|-------------|------------------|------------------|
| LEGAL_CONTRACT | 3 clauses | 4 clauses (+data breach) | 4 clauses |
| CREDIT_AGREEMENT | 4 clauses | 4 clauses (unchanged) | 4 clauses |
| EMPLOYMENT_CONTRACT | 4 clauses | 4 clauses | 5 clauses (+remote work) |
