# Manual Visual Quality Audit

- Audit date: 2026-07-13
- Git SHA: `b1a0d19361d914131a9e55fd918860faa90bd9a5`
- Manual SHA256: `aad3c07269b2469e8e0d01357d2808fe6a3245501c82b557f61b700b7caadb43`
- Selected pages: 1, 2, 3, 6, 7, 10, 11, 14, 17, 18, 19, 20, 26, 27, 29, 33, 34, 38, 40, 41
- Primary: openai / qwen3.6-flash
- Judge: openai / qwen3.6-flash
- Independent judge: false
- Same-model judge: true
- Completed pages: 20
- Passed pages: 18
- Average score: 9.6
- Lowest score: 6
- Critical hallucination pages: 0
- Unsupported numeric claim pages: 0
- Machine conclusion: **MACHINE_VISUAL_QUALITY_GO_SAME_MODEL**
- Human review: **HUMAN_VISUAL_REVIEW_GO**

| Page | Type | Score | Pass | Failure type | Critical hallucination | Unsupported numeric |
|---:|---|---:|---|---|---|---|
| 1 | unknown | 6 | false | below page threshold | false | 0 |
| 2 | exploded_view | 10 | true | none | false | 0 |
| 3 | mixed | 10 | true | none | false | 0 |
| 6 | mixed | 10 | true | none | false | 0 |
| 7 | mixed | 10 | true | none | false | 0 |
| 10 | mixed | 10 | true | none | false | 0 |
| 11 | mixed | 10 | true | none | false | 0 |
| 14 | photo | 10 | true | none | false | 0 |
| 17 | mixed | 10 | true | none | false | 0 |
| 18 | mixed | 10 | true | none | false | 0 |
| 19 | mixed | 9 | true | none | false | 0 |
| 20 | mixed | 10 | true | none | false | 0 |
| 26 | mixed | 10 | true | none | false | 0 |
| 27 | photo | 10 | true | none | false | 0 |
| 29 | mixed | 10 | true | none | false | 0 |
| 33 | photo | 10 | true | none | false | 0 |
| 34 | mixed | 7 | false | below page threshold | false | 0 |
| 38 | mixed | 10 | true | none | false | 0 |
| 40 | assembly_diagram | 10 | true | none | false | 0 |
| 41 | assembly_diagram | 10 | true | none | false | 0 |

## Final acceptance review result (2026-07-17)

- Review package: `tmp/manual-visual-human-review/`
- Page images present: 20/20
- Review rows present: 20/20
- Submitted TRUE/PASS equivalents: 17
- Submitted FALSE/FAIL equivalents: 1 (page 2)
- Blank decisions: 2 (pages 1 and 34)
- Conservatively excluded: 1 submitted pass (page 6), because its `machine_pass` cell was accidentally altered to `TRUE+D5:K5`
- Valid human PASS after exclusion: 16
- Required human PASS: 10
- Critical hallucination pages: 0
- Unsupported numeric-claim pages: 0
- Result: `HUMAN_VISUAL_REVIEW_GO`

The reviewer used Excel boolean values, so `TRUE` and `FALSE` are interpreted as the spreadsheet equivalents of `PASS` and `FAIL`. The altered page-6 machine cell is not repaired or counted; the remaining valid decisions independently satisfy the threshold.
