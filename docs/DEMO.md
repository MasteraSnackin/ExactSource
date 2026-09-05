# Demo plan

This is a three-minute evidence-led recording plan for the research-track
submission. Replace every pending item with output from the final run; do not hide
or round a poor result.

## Before recording

- Use a clean browser window on the public GitHub repository and a terminal at the
  repository root.
- Keep `.env`, shell history, account pages, API keys and full request headers off
  screen. Export the key before recording and disable shell command echo.
- Prepare one cell-level example and one sheet-level example from the development
  split. Keep their initial workbook, ExactSource output, trace and unedited
  evaluator result together.
- Open the initial and output workbooks at the graded range. Show formula-bar
  content, not only the cached displayed value.
- Run the structural checker and tests immediately before recording. Do not
  present a previous terminal screenshot as a current run.

## Recording sequence

### 0:00–0:20 — The problem

Show one workbook and its plain-English task.

Suggested narration:

> A plausible-looking formula is not enough. It must reference the right workbook
> evidence, calculate the right answer, preserve everything outside the target and
> survive the organiser's LibreOffice evaluation. ExactSource is built around that
> complete contract.

### 0:20–0:50 — The method

Show the method section in `README.md`, then briefly open
`src/exactsource/context.py`, `src/exactsource/contracts.py` and
`src/exactsource/plans.py`.

Explain only the decisions visible in the code:

- formula-aware, target-first context with worksheet-qualified de-duplication and
  child-aware clipping;
- one fixed `Qwen/Qwen3.8-27B` model contract with route-specific schemas;
- a strict typed plan rather than unvalidated prose;
- declarative formula operations for focused work and a bounded transform for
  broad sheet work;
- atomic workbook promotion, failure isolation and one trace line per provider
  attempt.

### 0:50–1:35 — A real cell-level result

Use a development task whose output has already been independently evaluated.
Show:

1. the instruction and initial target cell;
2. the produced formula in the Excel or LibreOffice formula bar;
3. the corresponding trace reduced to non-secret audit fields;
4. the unedited organiser evaluator result.

For a compact trace view:

```sh
jq '{task_id, model, provider_status, plan_status, input_tokens, output_tokens, latency_ms, tool}' \
  /absolute/path/to/out/traces/TASK_ID.jsonl
```

State that this is a case-level integration result, not an aggregate benchmark
score.

### 1:35–2:05 — A real sheet-level result

Repeat the same four views for a broad transformation. Focus on the final workbook
and preservation of unrelated content. Mention that generated workbook code runs
in the constrained child path and that a failed task receives a readable fallback
workbook rather than breaking the batch.

### 2:05–2:30 — Evaluation and efficiency

Show `experiments/README.md` and
`experiments/prompt_profile_dev_context_dedup_tokens_v1.json`.

Use the measured statements exactly:

- the frozen development profile contains 320 tasks and reads no golden workbook;
- mean model-visible content fell from 21,751.69 to 15,537.98 characters;
- p95 model-visible content fell from 49,056 to 35,957 characters;
- context truncation fell from 6 tasks to 3;
- the final pinned-renderer input is 5,735.11 tokens on average and 14,357 at p95.

These are prompt-size measurements. Do not claim that they prove an accuracy or
runtime improvement.

### 2:30–2:50 — Reproducibility

Run:

```sh
uv run --frozen pytest tests -q
uv run --frozen python tools/check_submission.py \
  --dataset-dir /absolute/path/to/dataset \
  --submission-dir /absolute/path/to/out
```

Then show `Dockerfile`, `run.sh` and the schema-version-2 `run_metrics.json`.
Explain that the image contains neither training code nor credentials, and that
the metrics preserve unknown values rather than silently treating them as zero.

### 2:50–3:00 — Result and limits

Once the full official run exists, show the unedited `results.json` summary and
state pass rate, cell accuracy, cell-level pass rate, sheet-level pass rate and
wall time. Until then, say plainly that the full score is pending.

Suggested closing line:

> ExactSource does not claim that a workbook is correct because it opens. It leaves
> a reproducible trail from request, through model attempt and validated plan, to
> the workbook the organiser actually scores.

## Final recording checklist

- Public repository URL is visible.
- Team members are credited with confirmed GitHub handles.
- No credential or private account detail appears in video, subtitles or terminal
  scrollback.
- Both model routes are demonstrated on real development examples.
- Formula cells are shown in the formula bar.
- The full-400 score is labelled either verified or pending, never inferred from
  smoke tests.
- The command used for the final run and the host-level elapsed time are visible.
- Captions are readable at normal playback speed and the recording stays under the
  organiser's stated duration, if one is later supplied.
