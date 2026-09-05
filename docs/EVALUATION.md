# Evaluation protocol

The public benchmark is useful for iteration, but repeatedly tuning against all
400 public golden workbooks would produce an unreliable result. ExactSource's
development protocol separates implementation checks from performance claims.

## Metrics

The organiser's evaluator defines the authoritative metrics after LibreOffice
recalculation:

- pass rate: proportion of tasks with every graded cell correct;
- cell accuracy: proportion of all graded cells correct;
- cell-level pass rate;
- sheet-level pass rate.

Pass rate is the primary ranking metric. Cell accuracy is reported, but it is
highly concentrated because a small number of sheet-level tasks contain most of
the benchmark's graded cells. Results should also be grouped by answer-size
bucket and transformation family.

## Development split

Before prompt or algorithm tuning, freeze an 80-task hold-out and use the
remaining 320 tasks for development. The split should be deterministic and
stratified by:

- cell-level versus sheet-level task;
- formula or transformation family;
- logarithmic answer-size bucket;
- presence of formulas in the initial workbook;
- multi-sheet structure;
- workbook truncation exposure;
- tables and defined names;
- macro or VBA wording.

The hold-out score is only inspected at deliberate checkpoints. The final
submission score must still use all 400 tasks and the unmodified organiser
evaluator with `--all`. Run that command from the organiser's `research/`
checkout; ExactSource does not vendor or silently modify `evaluate.py`.

## Required comparisons

At minimum, record these runs with the same model and temperature:

1. untouched initial workbook, to establish a no-op floor;
2. organiser one-shot baseline;
3. formula-preserving adaptive context with literal cell writes;
4. compact formula/fill operations;
5. two-route formula and sheet-transform solver;
6. final solver with one bounded repair pass.

Create the untouched-workbook control without a provider credential:

```sh
uv run python tools/make_copy_baseline.py \
  --dataset-dir /absolute/path/to/dataset \
  --out-dir /absolute/path/to/copy-baseline
```

The control writes the same workbook, prediction and trace layout as production,
but its trace explicitly records that it made zero model calls.

For each run, retain the original `run.log`, model traces, predictions,
workbooks and evaluator-produced `results.json`. Do not edit traces after the
run. A result is not a verified benchmark claim unless all expected tasks are
represented and the evaluator reports zero missing outputs.

Before a paid prompt ablation, profile request sizes on development IDs only:

```sh
uv run python tools/profile_prompts.py \
  --dataset-dir /absolute/path/to/dataset \
  --selection-file experiments/public_split_v1.json \
  --selection-field development_ids \
  --out experiments/prompt_profile_dev_context_dedup_v1.json
```

This command uses the production prompt path but makes no model request. It
reports characters and UTF-8 bytes. To measure the exact generation-prompt token
count with the pinned Qwen tokenizer and renderer, use the isolated training
environment and its already-cached tokenizer revision:

```sh
uv run --project training python tools/profile_prompts.py \
  --dataset-dir /absolute/path/to/dataset \
  --selection-file experiments/public_split_v1.json \
  --selection-field development_ids \
  --renderer-token-counts \
  --out experiments/prompt_profile_dev_context_dedup_tokens_v1.json
```

That mode forces tokenizer loading offline and still makes no provider request or
golden-workbook read. Provider-reported input and output tokens from completed
calls remain the authoritative live-run usage evidence.

## Leakage checks

Inference must produce the same set of artefacts when golden workbooks are
removed, renamed or unreadable. A source scan should also fail if runtime code
contains a golden-file glob or opens a path derived from a golden field.
Evaluator output may be used to measure a completed experiment; individual
golden mismatches must not be supplied to the solver as repair feedback.
