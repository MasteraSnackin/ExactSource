# Submission: ExactSource

This is a working submission draft. Fields marked **pending** must be replaced with evidence from the final official run before submission.

## Team

- Team name: ExactSource
- Members, one GitHub handle per line: **pending team confirmation**
- Repo URL: https://github.com/MasteraSnackin/ExactSource
- Demo video: **pending**

## What we built and why

ExactSource is a formula-aware spreadsheet reasoning system for the
SpreadsheetBench research task. Flat value prediction can hide useful formula
patterns, lose distant workbook context and scale poorly when a sheet-level task
changes thousands of cells. ExactSource instead inspects the initial workbook
without reading golden files and gives the fixed `Qwen/Qwen3.8-27B` model a
bounded, formula-preserving view of the relevant evidence.

Cell tasks receive an operations-only schema. Sheet tasks receive a mutually
exclusive operations-or-Python schema. The operations route supports formula
writes, relative fills, range copies and explicit clears inside the declared
answer ranges; broader sheet transformations can use restricted workbook code in
the submitted container. Context evidence is de-duplicated by worksheet and
coordinate, and large sections retain their structural headings before body
content is clipped.

The runtime validates plan structure, worksheet names, ranges, aggregate write
volume and newly introduced formulae before promoting a candidate workbook.
Formula checks cover prohibited capabilities, malformed delimiters and explicit
references to absent worksheets. They also reject a literal `VLOOKUP` or
`HLOOKUP` index that is provably outside a bounded static A1 range, but they do
not claim broader spreadsheet semantics or calculated results. Every streamed
provider attempt is traced.
Individual failures receive a readable initial-workbook fallback so the remaining
batch can finish.

Inference uses temperature zero, bounded retries and the unmodified base model.
An isolated 16-case synthetic SFT corpus has been validated offline, but it has
not been sent to Tinker or used to produce the submitted model. The public 400
golden workbooks are not used for inference or training. The final official score
and failure analysis are pending; this draft does not treat structural validation
as correctness evidence.

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

**Pending official full run. No score is claimed.**

Before submission, run the organiser's shipped evaluator with `--all --out results.json`, commit that unedited `results.json`, and replace this paragraph with its exact `summary` block. The required `items` value is 400.

## Your run on the 400

The following root artefacts are **pending generation by the final full run**:

- `predictions.jsonl`
- `outputs/`
- `traces/`
- `run_metrics.json`
- `run.log`
- `results.json`, produced afterwards by the organiser's evaluator

Do not treat the current draft as a submitted benchmark run until those files exist and pass both `tools/check_submission.py` and the shipped evaluator.

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
- `docs/TINKER_COOKBOOK.md`: isolated, optional SFT experiment plan and current
  permissions blocker.
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
