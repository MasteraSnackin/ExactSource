# Final 400-task run: post-run analysis

This document analyses the completed public benchmark run after inference and
evaluation had finished. None of these results, failure labels or evaluator
diagnostics was fed back into the model, recovery path or workbook generation.
The unchanged organiser evaluator output is retained at
[`results.json`](../results.json); the corresponding
[`full_400_8b84dba.json`](../experiments/full_400_8b84dba.json) is a sanitised
experiment record containing identities, aggregates and limited per-task
metadata, but no workbook contents, prompts, responses, formulas, credentials or
mismatch values.

## Headline result

The evaluator graded all 400 tasks. There were no missing submissions and no
evaluator errors. ExactSource passed 302 tasks, giving a **75.50% exact pass
rate**, and produced 238,486 correct graded cells out of 297,882, giving
**80.0606% cell accuracy**.

| Task type | Tasks | Exact passes | Pass rate | Correct cells | Graded cells | Cell accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Cell-level | 275 | 215 | 78.18% | 13,203 | 15,021 | 87.897% |
| Sheet-level | 125 | 87 | 69.60% | 225,283 | 282,861 | 79.644% |
| **Overall** | **400** | **302** | **75.50%** | **238,486** | **297,882** | **80.0606%** |

The two headline metrics answer different questions. Exact pass rate weights
every task equally and requires every graded cell in a task to be correct. Cell
accuracy weights large worksheets more heavily. Both are needed: the former
shows task-level reliability, while the latter captures how much of the total
graded workbook surface was correct.

## Generation and execution funnel

Every task received one initial call to `Qwen/Qwen3.8-27B`. Of those 400 first
calls, 292 produced plans that were accepted and applied: 198 cell-level and 94
sheet-level. Eighty-one reached their output-token limit before a complete
response (72 cell-level and nine sheet-level), 26 produced a plan that was
rejected during parsing or application (four cell-level and 22 sheet-level), and
one cell-level request ended in a provider transport failure.

ExactSource made 98 bounded second calls, for 498 model calls in total:

- 72 cell-level calls used the dedicated max-token recovery policy;
- 26 calls used the ordinary repair path after a plan or application rejection;
- no transport retries were made.

The second calls added 77 accepted plans: 63 from max-token recovery and 14 from
ordinary repair. The complete run therefore ended with 369 normally applied
outputs and 31 safe fallback workbooks. This runtime status is not a score. It
means only that the pipeline obtained and applied a structurally admissible
plan; correctness remained the evaluator's independent decision.

The 31 terminal fallbacks are fully accounted for by safe metadata. Nine
sheet-level initial calls exhausted their 32,000-token allowance. Nine recovered
cell-level calls also exhausted the 32,000-token recovery allowance. One
ordinary cell-level repair exhausted its 16,000-token allowance. Among repaired
sheet-level tasks, eight failed during sandboxed execution, two were rejected by
sandbox validation and one remained unparsable. The remaining fallback was the
initial provider transport failure. The fail-closed behaviour prevented these
cases from applying partial, malformed or disallowed transformations.

## What the recovery paths achieved

The special cell-level truncation recovery was useful, but not sufficient by
itself. Of 72 eligible tasks, 63 became runtime-accepted and 44 were exact
evaluator passes. Across all 72 tasks, it produced 4,819 correct cells out of
6,129. Among the 63 accepted recoveries, 44 were exact and 19 were structurally
valid but semantically wrong. In other words, the recovery converted 87.5% of
its cases into executable outputs, while 61.1% of all recovery cases became
exact passes. This difference is direct evidence that syntactic completion and
semantic correctness must be measured separately.

Ordinary repair handled 26 cases. Fourteen became runtime-accepted and 12 were
evaluator passes; notably, one evaluator-correct case remained a runtime
fallback. Broken down by the first rejection category:

| Initial rejection category | Repair cases | Runtime accepted | Evaluator passes |
|---|---:|---:|---:|
| Plan application | 2 | 2 | 1 |
| Parse | 7 | 5 | 3 |
| Sandbox validation | 9 | 5 | 5 |
| Sandbox execution | 8 | 2 | 3 |
| **Total** | **26** | **14** | **12** |

These groups are small, so they should not be treated as stable comparative
rates. They do show that repair adds real value after deterministic rejection,
including for sandbox-related failures, while also showing that a single repair
attempt cannot resolve every generated-program defect.

## Runtime success versus evaluator correctness

Of the 369 runtime-accepted tasks, 301 passed exactly and 183,297 of 186,878
graded cells were correct. Of the 31 fallbacks, one passed exactly and 55,189 of
111,004 graded cells were correct. The passing fallback was task `73-45`, for
which all 307 graded cells were correct. This is possible because a safe fallback
preserves the starting workbook, and the evaluator—not runtime status—determines
whether the requested result is present.

The type split exposes the main reliability gap. Cell-level execution produced
264 accepted outputs, of which 215 passed; none of the 11 cell-level fallbacks
passed. Sheet-level execution produced 105 accepted outputs, of which 86 passed;
one of the 20 sheet-level fallbacks passed. Once a plan was accepted, exact-pass
conversion was similar for cell-level and sheet-level tasks. The lower overall
sheet-level score is therefore driven substantially by execution attrition:
16.0% of sheet-level tasks fell back, compared with 4.0% of cell-level tasks.

Runtime acceptance is still not a semantic guarantee. Sixty-eight accepted
tasks were not exact. Forty-nine of those had no more than 20 incorrect graded
cells, and 12 missed exactness by one cell. At the other end of the distribution,
five accepted tasks with more than 100 incorrect cells accounted for 2,703 of
the 3,581 wrong cells in the accepted-output group. This suggests two distinct
improvement targets: deterministic coverage checks for near-misses and stronger
guardrails for high-blast-radius transformations.

## Graded-cell skew

The benchmark is highly skewed by workbook size:

| Graded cells in task | Tasks | Exact passes | Correct cells | Graded cells |
|---|---:|---:|---:|---:|
| 1 | 40 | 33 | 33 | 40 |
| 2–10 | 123 | 108 | 568 | 618 |
| 11–100 | 175 | 124 | 5,145 | 5,964 |
| 101–1,000 | 45 | 27 | 11,204 | 14,319 |
| More than 1,000 | 17 | 10 | 221,536 | 276,941 |

The 17 largest tasks contain 92.97% of all graded cells and 93.28% of all wrong
cells. Consequently, a small number of large sheet transformations dominate
cell accuracy, while they represent only 4.25% of task pass rate. Reporting only
one metric would hide this concentration. Future optimisation should monitor
both exact tasks and size-weighted cells, and should stratify results by task size
so that gains on many small tasks are not mistaken for gains on the dominant
worksheet surface.

The mismatch lists are diagnostic samples, not complete error inventories. The
evaluator retained 403 mismatch entries against 59,396 incorrect graded cells,
with at most five entries retained per task. Therefore neither the raw result's
mismatch list nor the sanitised record's `mismatch_count` should be summed as a
measure of total incorrect cells. The complete count is derived from `cells -
correct`; no conclusion here relies on undisclosed mismatch values.

## Latency and output-token efficiency

The coordinator measured 23,976.245 seconds for the run. Host end-to-end time
was 23,983.52 seconds—6 hours, 39 minutes and 43.52 seconds—and the separate
evaluator took 329.66 seconds. Per-task latency had a median of 149.882 seconds,
a p95 of 714.580 seconds and a maximum of 1,049.773 seconds. Runtime-accepted
tasks had a 133.111-second median; fallback tasks had a 605.703-second median.
Single-call tasks had a 95.460-second median, compared with 558.161 seconds for
max-token-recovery tasks and 469.789 seconds for ordinary-repair tasks.

The provider reported 5,592,930 output tokens across 498 calls: a mean of
11,230.8 and a median of 10,829 tokens per call, with p95 28,856 and maximum
32,000. At task level, the median was 9,497.5 output tokens, p95 was 42,018 and
the maximum was 49,910. Fallback tasks had a 32,000-token median, versus 8,517
for runtime-accepted tasks. Ninety-one calls hit a token ceiling—73 at 16,000
and 18 at 32,000—and only the 72 initial cell-level 16,000-token cases were
eligible for the dedicated recovery path. Long generations are therefore both a
reliability problem and the clearest latency and token-efficiency target.

The provider reported zero input tokens. ExactSource treats that field as
unavailable rather than as evidence of zero input usage, and makes no monetary
cost claim from it.

## Reproducibility boundary

All 498 calls requested temperature `0.0`, and the public evidence pins the
solver commit, model name, dataset and evaluator hashes, evaluator commit,
LibreOffice version, container image and platform. Those controls make the
method auditable and the run environment reconstructable. They do not prove
bit-for-bit deterministic model output. Temperature zero does not eliminate all
hosted-inference variability, and this submission does not contain a second full
400-task replicate. A rerun should therefore be expected to follow the same
procedure, but not assumed to reproduce every task outcome exactly.

## Highest-value next improvements

1. **Reduce sheet-level execution attrition.** Twenty of 125 sheet-level tasks
   fell back, accounting for almost two-thirds of all fallbacks. Safer
   first-class style and copying operations, plus clearer sandbox-compatible
   transformation patterns, should prevent recurring validation and execution
   failures without weakening the sandbox.
2. **Constrain long reasoning before it reaches a hard ceiling.** Earlier
   structured-output discipline, tighter route-specific context and adaptive
   reasoning budgets should reduce the 91 max-token events. Any sheet-level
   recovery policy should be tested against both accuracy and its substantial
   latency/token cost rather than added unconditionally.
3. **Add deterministic, golden-free semantic checks.** The 12 one-cell
   near-misses and the wider group of 49 accepted tasks with at most 20 wrong
   cells are candidates for checks on target coverage, output shape, preserved
   workbook invariants and reference validity. These checks must use only the
   request and input workbook.
4. **Guard high-blast-radius plans.** Large tasks dominate graded cells, and five
   accepted failures dominate wrong cells within the accepted group. Validation
   should become stricter as the number of affected cells grows, with compact
   pre-application summaries and deterministic post-application invariants.
5. **Ablate changes on frozen development splits.** Recovery, prompt and
   validator changes should be compared for exact pass rate, cell accuracy,
   fallbacks, latency and output tokens. This preserves the no-golden inference
   boundary and avoids tuning conclusions from a single temperature-zero run.

The central finding is that ExactSource's remaining error is not one failure
mode. Sheet execution failures, generation truncation and accepted-but-wrong
plans require different interventions. The recorded funnel makes those trade-offs
visible and gives future work measurable targets without leaking evaluator
answers into generation.
