# ExactSource SFT experiment

This directory is an isolated, optional training environment. It is excluded
from the submission image by the root `.dockerignore` allow-list and does not
change ExactSource's runtime dependencies.

The offline scaffold now contains 16 hand-authored synthetic cases: 12 fixed
training cases and 4 fixed tuning cases. Fourteen exercise declarative workbook
operations and two exercise the restricted Python sheet route. It uses no
benchmark question, benchmark initial workbook or golden output. During
preparation, every labelled plan is executed through the production path and
checked against complete answer-range and outside-range preservation assertions.
The 13 formula-bearing cases are then recalculated by headless LibreOffice and
compared with separately authored result values before export.

The checked local preparation completed successfully with the pinned tokenizer
and all 13 independent formula checks. It produced deterministic JSONL and a
hash-bearing manifest beneath the ignored `scratch/sft/` directory. This proves
only that the corpus can be reproduced and that its labelled plans pass those
checks. No paid Tinker training, sampler checkpoint, model comparison or full
benchmark run has been performed.

## Offline preparation

Prerequisites are Python 3.11–3.13, `uv`, headless LibreOffice, and the Qwen
tokenizer already present in the local Hugging Face cache at revision
`1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0` with vocabulary size `248044`.
Preparation forces Hugging Face offline mode and never creates a Tinker client.
It fails closed if that exact cached tokenizer is unavailable or if a rendered
example exceeds 32,768 tokens.

Corpus preparation finds `soffice` on `PATH`, uses the macOS application path, or
accepts an explicit `--soffice /absolute/path/to/soffice`. LibreOffice runs only
against temporary synthetic workbooks and the temporary profile is removed when
the check ends. The organiser's evaluator separately uses LibreOffice later when
comparing a checkpoint with the base model.

Prepare and verify the corpus with:

```sh
uv sync --project training --locked
uv run --project training exactsource-sft prepare
uv run --project training exactsource-sft train
```

The first command creates the isolated environment. `prepare` writes ignored
artefacts beneath `scratch/sft/`. `train` without `--execute` reconstructs the
JSONL from the reviewed case source, re-renders every train and tune example,
validates the proposed hyperparameters and hard pilot ceilings, and prints a
dry-run summary without creating a Tinker client.

The fixed training format is:

- base model: `Qwen/Qwen3.8-27B`;
- renderer: `qwen3_8_xhigh_reasoning`;
- target weighting: `LAST_ASSISTANT_MESSAGE`;
- maximum rendered length: 32,768 tokens, rejected rather than truncated;
- LoRA seed: 240905;
- assistant target: a plain strict `SolvePlan` JSON string.

With the Qwen3.8 reasoning renderer, a plain string assistant target represents
an empty thinking block followed by JSON. This is deliberately a schema/latency
ablation. It is not presented as a neutral formatting choice, and it must beat
the base model on workbook evaluation before promotion.

## Paid pilot gate

The paid path remains unavailable unless all four independent conditions are
present:

- the command includes `--execute`;
- `EXACTSOURCE_ALLOW_PAID_TRAINING` is exactly `YES`;
- `TINKER_API_KEY` is non-empty;
- `TINKER_PROJECT_ID` names a writable project and is non-empty.

Keep real values in the repository's ignored `.env` file or an approved secret
manager. Do not put an API key literal in the command line, shell history,
documentation or a committed file. For example, add the three assignments to the
ignored local `.env`, then export them only into the current shell before running:

```sh
set -a
. ./.env
set +a
uv run --project training exactsource-sft train --execute
unset EXACTSOURCE_ALLOW_PAID_TRAINING TINKER_API_KEY TINKER_PROJECT_ID
```

The command does not load `.env` itself and never prints either credential. The
`unset` line removes all three exported training variables from that shell after
the process ends; it does not alter `.env`. The run directory must be a new named
directory beneath `scratch/sft/runs`. The fixed pilot defaults to four batches of
two examples, evaluates the four tune examples before and after training, and has
immutable ceilings of 6 steps, 12 training examples and 50,000 aggregate
model-input tokens across selected training data and both tune passes. It uses
one deterministic LoRA seed and one permanent final state/sampler checkpoint. It
does not create periodic sampler checkpoints or modify the production model path.

Each authorised run stores the verified manifest, exact shuffled case order,
source/prompt/data hashes, dependency versions, batch case IDs, training and tune
loss, wall time, and a non-secret data fingerprint beside the checkpoint paths.

The current account's Default Tinker project is read-only. Supplying an API key
alone is therefore insufficient; a writable `TINKER_PROJECT_ID` is still needed.

## Acceptance

Synthetic execution and training loss are diagnostics, not benchmark evidence.
After an authorised pilot, sample the fixed checkpoint through the unchanged
ExactSource runtime on a predeclared development subset and score it with the
organiser's evaluator. Keep the frozen 80-task hold-out untouched. Promote a
checkpoint only when workbook accuracy improves without an unacceptable increase
in invalid plans, fallbacks, token use or wall time.
