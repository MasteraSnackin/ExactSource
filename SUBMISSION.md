# Submission: ExactSource

This submission draft contains the completed public benchmark evidence. The team
list and demo-video URL remain pending user input.

## Team

- Team name: ExactSource
- Members, one GitHub handle per line: **pending team confirmation**
- Repo URL: https://github.com/MasteraSnackin/ExactSource
- Demo video: **pending**

## What we built and why

ExactSource is a formula-aware SpreadsheetBench solver built to retain workbook
context and produce auditable edits rather than predict isolated values. It
inspects only the task metadata, instruction and initial workbook, then gives the
fixed, unmodified `Qwen/Qwen3.8-27B` model a bounded formula-preserving view of
relevant cells. Cell tasks receive a typed operations-only schema; sheet tasks
receive mutually exclusive operations or restricted Python, allowing formula
writes, relative fills, range copies, explicit clears and larger transformations
without changing the model. Before publishing a candidate, the runtime validates
plan structure, worksheet names, declared ranges, aggregate write volume and
newly introduced formulae, and then reopens the workbook. Each streamed provider
attempt is traced after secret redaction. A failed task receives a readable copy
of its initial workbook so one failure does not stop the batch. The completed
clean-start run used temperature zero and bounded retries, with no golden
workbook access, golden-value lookup step, second model or fine-tuning. The
organiser's unchanged evaluator graded all 400 outputs: overall pass rate
`0.755`, cell accuracy `0.8006`, cell-level pass rate `0.7818` and sheet-level
pass rate `0.696`. These results do not erase the limits: 31 tasks used safe
fallbacks, runtime success is not correctness, repeated temperature-zero
completions varied during development, unsupported data-validation extensions
may be removed by `openpyxl`, and provider input-token counts were unavailable.

## Models

- Inference provider: Tinker, Anthropic-compatible streaming endpoint
- Exact model ID fixed in source: `Qwen/Qwen3.8-27B`
- Trace model name: `tinker:Qwen/Qwen3.8-27B`
- Temperature: `0`
- Cell initial request and ordinary semantic repair: maximum `16,000` completion
  tokens with reasoning requested through the model's supported Boolean setting
- Sheet initial request and ordinary semantic repair: maximum `32,000` completion
  tokens with reasoning requested through the model's supported Boolean setting
- Initial-cell truncation recovery: only an initial cell request that stops at
  `max_tokens` receives one fresh `32,000`-token request with Boolean reasoning
  disabled, `/no_think` appended and an empty-thinking assistant prefill. This is
  no-think-requested, not a guarantee that the provider emits no reasoning
- Recovery boundary: truncated content is not replayed; the recovery consumes
  the sole second-call allowance and can never lead to a third logical call
- Other inference models: none; no second model is used as a router, judge,
  verifier or fallback
- Fine-tuning: none; no paid training run or checkpoint has been created
- Prepared but unused training data: 16 hand-authored synthetic cases, fixed as
  12 training and 4 tuning examples and validated offline through the production
  execution paths; 13 formula cases also passed independent LibreOffice result
  checks
- Use of the public 400 golden workbooks for training or inference: none

One environment variable is required at inference time: `TINKER_API_KEY`. It is passed at container runtime and is not stored in the repository or image.

For completed but invalid plans, the sole second call is instead an ordinary
semantic repair at the route's normal budget and with reasoning requested. A
sheet truncation, a truncation during an ordinary repair or a truncated cell
recovery falls back without another logical call. Each logical call retains its
separate bounded transport-retry policy. Captured response content is retained
in traces after secret redaction.

The optional paid SFT pilot is outside the current inference claim. It requires
all four conditions `--execute`, `EXACTSOURCE_ALLOW_PAID_TRAINING=YES`, a
non-empty `TINKER_API_KEY`, and a non-empty writable `TINKER_PROJECT_ID`. Secrets
must be exported from the ignored local `.env` file or a secret manager, never
placed as inline command literals, and should be removed from the shell with
`unset EXACTSOURCE_ALLOW_PAID_TRAINING TINKER_API_KEY TINKER_PROJECT_ID` after
the command.

## Scores on the 400

The organiser's unchanged evaluator graded all `400` predictions: `400` items,
`0` missing and `0` evaluator errors.

| Official metric | Result |
| --- | ---: |
| Overall pass rate | `0.755` (75.5%) |
| Cell accuracy | `0.8006` (80.06%) |
| Cell-level pass rate | `0.7818` (78.18%) |
| Sheet-level pass rate | `0.696` (69.6%) |

The evaluator took `329.66` seconds and used LibreOffice 26.8.0.3 to recalculate
the submitted workbooks. It ran from organiser commit
`37d9016264762a25cae49e077cd0893055bd9093`; the evaluated `evaluate.py` had SHA-256
`8840a0e93df958d41dc5892ee42b33210ba773c1e0b73b691bbaf7d06a84d46b`.

## Your run on the 400

The full run started from a clean worktree at solver commit
`8b84dba1d9263e2123b8f15267239b70ff817907`. It ran
`Qwen/Qwen3.8-27B` through Tinker from `2026-09-06T00:10:23Z` to
`2026-09-06T06:50:07Z`. The host elapsed time was `23,983.52` seconds. The run
produced 400 predictions, 400 workbooks and 400 task trace files containing 498
trace records. ExactSource reported 369 runtime successes and 31 safe
initial-workbook fallbacks; runtime success means structural acceptance, not a
correct benchmark answer.

The provider reported `5,592,930` output tokens. It reported input-token values
as zero, which are treated as unavailable rather than as zero usage. No paid
fine-tuning or checkpoint was used.

Run provenance:

- Dataset `dataset.json` SHA-256:
  `bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7`
- Solver commit: `8b84dba1d9263e2123b8f15267239b70ff817907`
- Docker image: `sha256:ce130c19891d54a78f6071d9e8e85868c3e92c6ac7e093d60a7b76fe532de50b`
  on `linux/arm64`
- Locked CI for the solver commit:
  https://github.com/MasteraSnackin/ExactSource/actions/runs/34000060789
- Organiser evaluator commit:
  `37d9016264762a25cae49e077cd0893055bd9093`
- `evaluate.py` SHA-256:
  `8840a0e93df958d41dc5892ee42b33210ba773c1e0b73b691bbaf7d06a84d46b`
- LibreOffice: `26.8.0.3`

Seven scored output workbooks retain external-link metadata inherited from the
supplied public initial workbooks. ExactSource introduced none of those targets,
and they were retained so the published files remain the artefacts that were
evaluated. Some are HTTPS targets that a spreadsheet client may contact if link
updates are enabled; inspect the files with external updates disabled. The exact
task IDs, attribution and licence boundary are recorded in `PROVENANCE.md`.

The reviewed final artefacts are present at the repository root:

- `predictions.jsonl`
- `outputs/`
- `traces/`
- `run_metrics.json`
- `run.log`
- `results.json`, produced by the organiser's evaluator after inference

`tools/check_submission.py` passed this layout with 400 predictions, 400
workbooks, 400 trace files, 498 trace records and 31 recorded task failures. The
public, non-secret aggregate records are
[`experiments/acceptance_10_8b84dba.json`](experiments/acceptance_10_8b84dba.json)
and [`experiments/full_400_8b84dba.json`](experiments/full_400_8b84dba.json).

## Code

The reproducible runtime is defined by `Dockerfile` and starts `exactsource` with no arguments. It reads only `/data`, mounted read-only, and writes to `/out`. For a local one-command run after configuring `TINKER_API_KEY`:

```sh
./run.sh /absolute/path/to/dataset /absolute/path/to/out
```

Model ID, temperature, budgets, retry bounds and concurrency are fixed in `src/exactsource/config.py`. The image includes application source and locked runtime dependencies only; datasets, outputs, `.env` files and VCS history are excluded by an allow-list `.dockerignore`.

The final run writes schema-version-2 `run_metrics.json` atomically after
validating all task artefacts. It reports batch-execution wall time, task
success/failure totals, logical model calls, provider attempts, provider and plan
status counts, semantic repairs, transport retries, stage timings and
prompt/response character counts. Semantic repairs retain a compatibility total
and are split into ordinary repairs, max-token recoveries and an explicit
other-or-unknown bucket. Per-task latency evidence preserves timings for
failures that correctly have no model trace. Latency and character distributions
record known and unknown counts, sum, minimum, exact median, nearest-rank p95 and
maximum.
Token totals retain separate known- and unknown-attempt counts.
Input-token values are summed as reported by the trace and are not inflated by
adding the separately reported cache fields a second time. This timer covers task
execution through structural validation, not dataset loading, solver construction,
metrics publication or Docker startup. The metrics file labels these values as
coordinator-clock evidence. Its checker can cross-check non-empty terminal traces,
but an empty pre-model trace cannot independently prove its task latency. Retain a
separate host-level
`/usr/bin/time -p ./run.sh ...` result with the final traces for the full elapsed
submission-run evidence.

The organiser's evaluator, not the ExactSource inference image, requires headless
LibreOffice to recalculate output workbooks. Optional SFT corpus preparation is
also outside the image; it uses LibreOffice only on temporary synthetic outputs
and requires the exact pinned Qwen tokenizer revision in the local Hugging Face
cache. Tokenizer loading runs with network access disabled.

## Things to look at

- `docs/ARCHITECTURE.md`: trust boundaries, routing and failure isolation.
- `docs/EVALUATION.md`: score discipline, held-out evaluation and failure analysis plan.
- `docs/FINAL_RUN_ANALYSIS.md`: post-run correctness, recovery, failure, latency
  and output-token analysis that was not fed back into inference.
- `docs/TINKER_COOKBOOK.md`: isolated, optional SFT experiment plan and explicit
  paid-run gates; no SFT run was performed.
- `training/README.md`: validated 16-case synthetic corpus, offline preparation
  contract and explicit paid-run gate.
- `experiments/sft_preflight_v1.json`: non-secret hashes, exact renderer token
  counts, independent formula-check evidence and the capped dry-run projection.
- `experiments/prompt_profile_dev_context_dedup_tokens_v1.json`: development-only
  production-prompt sizes measured with the pinned offline Qwen renderer.
- `docs/ORGANISER_CLARIFICATIONS.md`: dated Discord rules, conservative
  interpretation and unresolved questions.
- `docs/DEMO.md`: an evidence-led three-minute recording plan and disclosure
  checklist.
- `PROVENANCE.md`: pinned organiser revision, dataset checksums and licensing boundary.
- `tests/`: deterministic tests for dataset confinement, workbook operations, sandboxing and judge artefacts.
- `tools/check_submission.py`: a golden-free structural check for predictions,
  workbooks, traces, aggregate run metrics and logs.
