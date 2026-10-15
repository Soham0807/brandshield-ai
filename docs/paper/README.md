# Research paper — first draft

Two versions of the same paper, both first drafts built from the real numbers this project
produced (no invented results):

| File | Use it for |
|---|---|
| `BrandShieldAI_paper.md` | Paste into Word / Google Docs. Tables are Markdown, so they paste as real tables. |
| `BrandShieldAI_paper.tex` | Overleaf (IEEEtran, `conference` mode, compile with pdfLaTeX). This is the version to submit. |
| `fig1_architecture.png` | Figure 1 — layered architecture (copy of `docs/uml/03-component-diagram-wide.png`). |
| `fig2_integrations.png` | Optional Figure 2 — YouTube/Instagram class diagram (copy of `docs/uml/04-class-diagram-social-integrations.png`). |

Format assumed: **IEEE conference, double column, ~6 pages.** That is the standard for a
final-year project paper and for most student conferences. If your faculty wants Springer
LNCS, Elsevier, or a fixed college template instead, say so and the `.tex` can be switched
over — only the preamble and the author block change, the content stays.

---

## Where every number in the paper comes from

All results are measurable from this repository. Nothing is estimated.

| Claim in paper | Source |
|---|---|
| D1: Acc 0.8313 / macro-F1 0.8174 (ensemble hybrid), 0.7904 (models only); DistilBERT 0.7831 / 0.7764 | `backend/scripts/evaluate_model.py` (results in `backend/data/evaluation.json`) |
| D4: Acc 0.7400 / macro-F1 0.7276 on 200 random real comments; DistilBERT 0.665 | same script, `backend/eval/real_comments_labeled.csv` |
| Per-class P/R/F1 and confusion matrix | same script |
| Aspect detection P 0.900 / R 0.730 / F1 0.806 | same script, aspect-annotated subset |
| 79.7% agreement with star ratings (385/483); DistilBERT 74.7% | App Store reviews in the live DB, rating mapped 1–2/3/4–5 |
| 12,174 mentions; 11,063 YouTube / 135 Instagram / 491 news / 483 App Store / 2 CSV | live SQLite database |
| 32.4 ms/comment (D1), 120 ms (D4), batch 32, CPU, two models | evaluation script timing |
| ~140 ms single comment incl. HTTP; ~2 GB resident memory | measured on the running process |
| Crisis detected in 24 s, risk 20 → 79 | controlled crisis-injection run on live data |
| 4 false positives removed by share-based threshold | anomaly threshold ablation |
| Earlier model: 49.4% acc / 40.6% macro-F1 | evaluation of the first candidate model |

**Re-run before submission** so the figures match the database on the day you submit — the
corpus keeps growing while the system is polling.

---

## What you must fill in (do these in order)

1. **Author block** — add every team member's email in both files (`% TODO` markers in the
   `.tex`). Check with your guide whether Dr. Medhane is listed as a co-author or only in the
   acknowledgement; the draft currently lists him as a co-author.
2. **Verify all 12 references yourself.** They are real, well-known papers, but page numbers
   and venue details must be checked against Google Scholar or the ACL Anthology before you
   submit — do not trust them as typed. Also delete refs [10]–[12] if you never cite them in
   the body; an uncited reference is a reviewer's first complaint.
3. **Figure 1** — uncomment the `figure` block in the `.tex` (Section III) and upload
   `fig1_architecture.png` to Overleaf. A paper with no figure reads as unfinished.
4. **Add a results figure.** The strongest candidate is `docs/report/figures/ui-crisis.png`, the
   Trends page during the crisis experiment with the risk score at 79. A time-series plot of
   negative share with the detected anomaly marked would be even better.
5. **Re-run the evaluation** and update Tables II–IV if any number moved.
6. **Cut to the page limit.** If you are over 6 pages, the Limitations list compresses well
   into one paragraph, and Section VI-G (Discussion) can go entirely.

---

## Honest notes on the draft

Read these before your faculty does, so you are not caught out:

- **The benchmark is small (83 comments, one annotator).** This is the draft's weakest point
  and a reviewer will raise it. The paper states it plainly in Limitations rather than hiding
  it — that is the right move, but if you have two days, the highest-value work you can do is
  have two team members independently label 200–300 comments and report Cohen's kappa. That
  single change would lift the paper substantially.
- **The hybrid gain is small** (+2.7 macro-F1 on D1) and not statistically significant at n=83.
  The draft says so. Do not let anyone rewrite that into a stronger claim.
- **The 24 s crisis latency is from an injected surge**, not a real incident. The draft labels
  it a lower bound. Keep that wording.
- **Novelty is in the integration, not in any single algorithm.** RoBERTa, XLM-RoBERTa, Isolation Forest
  and Prophet are all off the shelf. The paper is positioned as a systems paper with an
  empirical evaluation, which is what it honestly is, and the contributions list is worded to
  match. If a reviewer asks "what is new?", the answer is: aspect-level attribution wired into
  a live crisis detector, direction-aware share-based thresholding, and evaluation on
  code-mixed Indian brand conversation — and the ablations back all three.

---

## Suggested venues

Student/early-career conferences that fit a systems-and-evaluation paper of this scale, in
rough order of fit: IEEE I2CT, IEEE PuneCon, IEEE CONECCT, ICCUBEA (Pune), and Springer ICDAM.
Ask your guide — they will know which ones your department has published in and what the
internal deadlines are.

## Converting to Word

No pandoc on this machine. Either paste `BrandShieldAI_paper.md` into Word directly (tables
survive), or install pandoc and run:

```
pandoc BrandShieldAI_paper.md -o BrandShieldAI_paper.docx
```
