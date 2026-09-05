# Tinker Cookbook experiment path

This document records ExactSource's isolated preparation path for
[`thinking-machines-lab/tinker-cookbook`](https://github.com/thinking-machines-lab/tinker-cookbook)
without adding its training dependencies to the judging image. An offline
synthetic SFT corpus is implemented and validated; this is not a claim that
ExactSource has been fine-tuned.

## Current status

- The submitted runtime uses Tinker's Anthropic-compatible streaming endpoint
  directly and fixes the model to `Qwen/Qwen3.8-27B`.
- The supplied credential has passed live compatible-API inference checks.
- Native SDK session creation is currently blocked because the account's Default
  project is read-only. Training needs an accessible writable project ID supplied
  as `TINKER_PROJECT_ID` or a permissions change by the project manager.
- `training/cases/synthetic_v1.json` contains 16 independently authored cases,
  fixed as 12 training and 4 tuning examples. Offline preparation successfully
  executed all 14 operations plans and 2 restricted-Python plans, verified their
  complete answer ranges and outside-range preservation, recalculated all 13
  formula-bearing cases with LibreOffice against independent value oracles,
  rendered them with the pinned Qwen tokenizer, and emitted deterministic JSONL
  plus a hash-bearing manifest.
- No Tinker training run, checkpoint or aggregate 400-task model run has been
  performed yet.

## Why the cookbook is useful

The cookbook solves three training-specific problems that should not be re-created
inside the production agent:

1. It chooses the model tokenizer and recommended renderer so supervised examples
   use the same chat representation as sampling.
2. It provides pipelined LoRA/SFT loops, checkpoint management and periodic
   evaluators.
3. It exposes sampler checkpoints as `tinker://.../sampler_weights/...` paths that
   the compatible inference endpoint can use as its model value.

The organiser's own Tinker baseline uses the same cookbook renderer-selection
utilities. The organiser checkout currently locks `tinker==0.27.1` and
`tinker-cookbook==0.5.7`; any ExactSource training environment should start from
those exact versions and record any deliberate upgrade.

ExactSource also pins `openpyxl==3.1.5`, `pydantic==2.13.5` and
`transformers==5.5.4` directly in the isolated training project. The tokenizer is
loaded in offline mode from revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0`; that revision must already exist in
the local Hugging Face cache. A missing or different tokenizer is a preparation
failure, not a reason to fetch an unrecorded replacement.

The default cookbook installation also brings sizeable training dependencies,
including PyTorch and renderers. Keeping those in a separate training environment
preserves the small, fast and auditable Docker runtime.

Headless LibreOffice is used during offline preparation to recalculate only the
temporary synthetic formula workbooks and prove that formula labels have the
intended values. It is not used by SFT itself. The organiser's evaluator also
needs LibreOffice later to recalculate benchmark outputs when a trained
checkpoint is compared with the base model.

## Submission constraints to preserve

The organiser clarified on 5 September 2026 that every model used by the final
research submission must be `Qwen/Qwen3.8-27B`. Deterministic tooling such as
LibreOffice is allowed. There is no stated hard time limit for the 400-task run,
but speed and method contribute to judging. Internet access is allowed when every
required key is declared and the run remains easy to reproduce.

Consequently:

- do not use another model as a teacher, judge, router or fallback;
- do not make the model ID runtime-selectable;
- keep credentials in environment variables only;
- retain one ordered trace line per model call;
- record wall time, attempts, known token totals and unknown-usage counts locally;
- never put golden values, golden workbooks or a golden lookup step in inference
  prompts or traces.

One point still needs explicit organiser confirmation before any benchmark data
is used for training: whether the public 400 golden workbooks may be used as
disclosed training labels. The submission template asks teams to state whether
they were used, but that question alone is not permission. Until clarified, keep
the frozen 80-task hold-out untouched and use only synthetic or independently
authored labels.

## Implemented offline scaffold and next experiment

The implemented corpus isolates the first question: whether SFT makes the model
return shorter, valid `SolvePlan` JSON more reliably. It does not try to teach all
spreadsheet logic at once. Its JSONL is not benchmark evidence and has not yet
been sent to Tinker.

1. Keep `experiments/public_split_v1.json` unchanged and the frozen 80-task
   hold-out untouched while choosing hyperparameters.
2. Continue using the exact production system prompts and bounded workbook
   context builder. Each synthetic assistant target is one strict `SolvePlan`
   JSON object, with no prose or hidden golden lookup.
3. Preserve the implemented 12/4 synthetic split and its deterministic formula
   writes, relative fills, cross-sheet references, error handling and restricted
   sheet-level Python cases.
4. If the organiser explicitly permits public-golden training, add labels derived
   only from the development subset and disclose the exact IDs and derivation.
   Cell-level labels can be generated deterministically from changed target cells.
   Do not invent noisy sheet-level code labels merely to increase dataset size.
5. Run the single capped LoRA pilot on the fixed Qwen model. Retain per-step loss,
   duration and token records, plus one permanent final state/sampler checkpoint;
   do not multiply paid runs or periodic checkpoints before the first result is
   evaluated.
6. Evaluate checkpoints through the unchanged ExactSource execution path and the
   organiser's shipped evaluator. Compare pass rate, cell accuracy, plan-rejection
   rate, fallback rate, calls per task, output tokens and wall time against the
   base-model run.
7. Select a checkpoint using the development/tuning results. Use the frozen
   80-task hold-out once for an honest confirmation, then report failures as well
   as aggregate metrics.

SFT is successful only if workbook accuracy improves without causing enough extra
latency or malformed plans to erase the gain. A lower training loss is not an
acceptance criterion.

## Paid-run authority and secrets

A paid run requires all four conditions simultaneously: `--execute`,
`EXACTSOURCE_ALLOW_PAID_TRAINING=YES`, a non-empty `TINKER_API_KEY`, and a
non-empty writable `TINKER_PROJECT_ID`. The command verifies the prepared hashes
before checking that gate. It also reconstructs the JSONL from the reviewed
synthetic source, validates IDs and provenance, renders every train and tune
conversation, validates the hyperparameters, and enforces fixed ceilings of 6
steps, 12 training examples and 50,000 aggregate model-input tokens. The default
pilot selects 8 training examples in a seeded order and evaluates all 4 tuning
examples before and after training.

Store real values only in the repository's ignored `.env` file or an approved
secret manager, then export them into the current shell. Do not put a key literal
on a command line:

```sh
set -a
. ./.env
set +a
uv run --project training exactsource-sft train --execute
unset EXACTSOURCE_ALLOW_PAID_TRAINING TINKER_API_KEY TINKER_PROJECT_ID
```

The CLI does not load `.env` automatically. Unsetting the three names after the
run clears the exported values and explicit paid-run acknowledgement from the
current shell without modifying the ignored file.

## Promotion into ExactSource

After a checkpoint wins the predeclared comparison and the organiser confirms that
such a checkpoint satisfies the Qwen-only rule:

1. Save sampler weights and remove their TTL so the judges can still access them.
2. Replace the fixed source model value with that exact `tinker://` sampler path;
   retain `Qwen/Qwen3.8-27B` as the declared base model in `SUBMISSION.md`.
3. Re-run transport contract tests because a checkpoint path changes the returned
   model identity seen in the SSE stream.
4. Rebuild both AMD64 and ARM64 Docker images, run the structural submission
   checker, and execute the official full-400 evaluator.
5. Record training data provenance, steps, learning rate, LoRA rank, compute, wall
   time and checkpoint path in `SUBMISSION.md`, as required by the organiser.

Do not promote a checkpoint merely because it can be sampled. Promotion requires
measured improvement on held-out workbooks and a reproducible checkpoint lifetime.
