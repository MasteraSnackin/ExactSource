# Three-minute demo script

This script presents the completed research-track submission using the public
artefacts at the repository root. Record the repository, terminal and workbook
views directly; do not invent a separate product interface.

## Before recording

- Use a clean browser window on the public repository and a terminal at its root.
- Keep `.env`, shell history, Tinker account pages, API keys, request headers and
  raw trace content off screen. Disable shell command echo before exporting a key.
- Prepare one passing cell task and one passing sheet task from the development
  data. `41691` and `13-1` are suitable verified examples. Have each source
  workbook, task instruction, `outputs/<TASK_ID>.xlsx` and
  `traces/<TASK_ID>.jsonl` ready.
- Show formulas in the Excel or LibreOffice formula bar rather than relying on a
  cached displayed value.
- Keep external-link updates disabled when opening benchmark workbooks. Seven
  evaluated outputs retain link metadata inherited from the public source data;
  the provenance document lists their task IDs and handling boundary.
- Do not rerun the paid 400-task inference during the recording. The committed
  artefacts are the evidence from that completed run.

## 0:00-0:20 — The problem

Show a source workbook beside its plain-English instruction.

Suggested narration:

> Spreadsheet formulas can look plausible while referencing the wrong range or
> changing the wrong cells. ExactSource turns a natural-language task into a
> workbook edit, validates the proposed operation and declared edit scope, and
> leaves the output and model trace available for independent evaluation.

## 0:20-1:00 — From instruction to workbook

Open the source workbook for cell task `41691`, then
`outputs/41691.xlsx`. Show the target in the formula bar. Repeat briefly with the
sheet task `13-1` and `outputs/13-1.xlsx`, pointing out that content outside the
requested scope remains present.

Suggested narration:

> These are development examples from the supplied benchmark, not hand-written
> mock-ups. The cell route produces focused formula operations. The sheet route
> can use compact operations, as this example does, or run a broader restricted
> transform in a constrained child process. Both routes use the required
> `Qwen/Qwen3.8-27B` model.

Do not claim fine-tuning: this submission uses prompting, structured plans,
deterministic validation and bounded repair around the fixed model.

## 1:00-1:35 — The method

Show the architecture in `README.md`, followed by a quick view of
`src/exactsource/context.py`, `src/exactsource/contracts.py` and
`src/exactsource/plans.py`.

Suggested narration:

> ExactSource builds target-first, formula-aware workbook context and asks the
> model for a typed plan rather than free-form code. The plan is checked before it
> is applied. Workbook promotion is atomic, so a rejected or failed attempt cannot
> leave a half-written submission file. Repair is bounded, keeping the method
> reproducible rather than looping until an answer happens to pass.

## 1:35-2:00 — Trace and failure handling

Show only non-secret audit fields from one committed trace:

```sh
jq -s 'map({task_id, step, semantic_attempt, model, provider_status, plan_status, output_tokens, latency_ms})' \
  traces/41691.jsonl
```

Then show the aggregate execution fields:

```sh
jq '{tasks, calls: .model.calls, attempts: .model.attempts,
     semantic_repairs: .reliability.semantic_repairs,
     transport_retries: .reliability.transport_retries}' run_metrics.json
wc -l traces/*.jsonl | tail -1
```

Suggested narration:

> The run produced 498 model-call trace records. Of 400 tasks, 369 completed the
> model-and-apply path and 31 received safe fallback workbooks. A runtime success
> is not treated as proof of correctness; only the unchanged organiser evaluator
> determines that.

## 2:00-2:40 — Verified 400-task result

Run this against the committed evaluator output:

```sh
jq '.summary' results.json
```

Keep the full summary visible while saying:

> All 400 tasks were graded, with zero missing outputs and zero evaluator errors.
> The verified pass rate is 0.755 and cell accuracy is 0.8006. The cell-level pass
> rate is 0.7818; the sheet-level pass rate is 0.696. The complete inference run
> took 23,983.52 seconds on the host, and the organiser evaluation took 329.66
> seconds. The lower sheet-level result is a real limitation, not a hidden or
> rounded-away result.

Briefly open `experiments/full_400_8b84dba.json` to show the pinned solver commit,
dataset hash, evaluator commit, container identity, timings and sanitised run
metadata. Do not scroll through mismatch details during the video.

## 2:40-3:00 — Reproducibility and close

Show `Dockerfile`, `run.sh`, `run_metrics.json`, `predictions.jsonl`, `outputs/`
and `traces/`. If time permits, show the already-completed structural check rather
than starting another model run:

```sh
uv run --frozen python tools/check_submission.py \
  --dataset-dir /absolute/path/to/dataset \
  --submission-dir "$PWD"
```

Suggested closing line:

> ExactSource does not claim a workbook is correct merely because it opens. The
> public repository provides the code, container entry point, 400 predictions,
> 400 output workbooks, 498 attempt traces and the unchanged evaluator result, so
> the method and its limits can be checked end to end.

## Recording checklist

- The public repository URL is visible and the final video link is added to the
  submission form and repository documentation after upload.
- No credential, private account detail, raw request header or shell history is
  visible in the video, subtitles or terminal scrollback.
- Both the cell and sheet routes are shown with real development examples.
- The formula bar is visible for formula cells.
- The result is labelled as the verified public 400-task benchmark, not a private
  held-out score.
- The five score fields, 369 runtime successes, 31 safe fallbacks, 498 trace
  records and both measured timings are stated exactly.
- Runtime success and evaluator correctness are kept distinct.
- The limitations are explicit: 31 tasks fell back safely, the sheet-level pass
  rate is 0.696, no fine-tuning was used, and provider-reported input-token usage
  is unavailable rather than zero-cost.
