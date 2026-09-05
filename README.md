# ExactSource

[![CI](https://github.com/MasteraSnackin/ExactSource/actions/workflows/ci.yml/badge.svg)](https://github.com/MasteraSnackin/ExactSource/actions/workflows/ci.yml)

ExactSource turns a written SpreadsheetBench instruction and an initial Excel
workbook into an edited workbook with a trace of how it was produced. It is the
Track 1 research entry for the Ylookup × Encode Rebuild Private Markets
Hackathon.

Cell-level tasks use typed spreadsheet operations. Sheet-level tasks can use the
same operations or a restricted Python transform. Every model call uses
`Qwen/Qwen3.8-27B` through Tinker.

## Contents

- [Quick start](#quick-start)
- [How it works](#how-it-works)
- [Outputs and official score](#outputs-and-official-score)
- [Known limits](#known-limits)

## Quick start

You need:

- Docker with a running engine
- A SpreadsheetBench-format dataset containing `dataset.json`
- A Tinker API key in the shell as `TINKER_API_KEY`
- Outbound HTTPS access

The dataset is not bundled. ExactSource was developed against the organiser's
[pinned research revision](https://github.com/ylookup/encode-hackathon/tree/37d9016264762a25cae49e077cd0893055bd9093/research).

The Docker run does not require `uv` or LibreOffice on the host. The structural
checker, local CLI and test commands below require
[`uv`](https://docs.astral.sh/uv/). The official evaluator also requires
headless LibreOffice.

Keep the API key outside the repository. If you use the git-ignored `.env` file
shown by [`.env.example`](.env.example), load it into the current shell and run:

```sh
set -a
. ./.env
set +a
./run.sh /absolute/path/to/dataset /absolute/path/to/out
unset TINKER_API_KEY TINKER_PROJECT_ID EXACTSOURCE_ALLOW_PAID_TRAINING
```

`run.sh` does not load `.env` itself. It builds `exactsource:local`, passes the
existing key by environment-variable name, mounts the dataset at `/data` as
read-only and writes results to `/out`. The first build needs network access to
pull the pinned images and install the locked packages.

ExactSource does not clear the output directory. It overwrites files for tasks
in the current run but leaves unrelated files in place. Use an empty output
directory for the final run.

## Current evidence

ExactSource has not completed the official 400-task run, so this README does not
report an aggregate score. The repository contains clearly labelled development
controls and one-task integration results. [`SUBMISSION.md`](SUBMISSION.md)
records the remaining evidence needed for the final submission.

The optional training workspace contains 16 hand-written synthetic cases, split
into 12 training examples and four tuning examples. Offline preparation used the
pinned Qwen tokenizer, and LibreOffice checks passed for all 13 cases containing
formulas. We have not run paid training or created a checkpoint. These cases have
not changed the submitted inference model.
[`training/README.md`](training/README.md) records what was validated and what
has not yet been run.

## How it works

```mermaid
flowchart TD
    accTitle: ExactSource workbook processing flow
    accDescr: A dataset task becomes workbook context, a model plan and either built-in operations or a restricted sheet transform. ExactSource writes per-task evidence, validates the full batch, records run metrics and passes predictions plus workbooks to the external evaluator.
    Input["Task instruction and initial workbook"] --> Loader["Confined dataset loader"]
    Loader --> Context["Workbook inspector and context builder"]
    Context --> Model["Qwen/Qwen3.8-27B through Tinker"]
    Model --> Plan["Validated SolvePlan"]
    Plan --> Route{"Execution route"}
    Route -->|"Cell task: operations"| Operations["Built-in workbook operations"]
    Route -->|"Sheet task: operations"| Operations
    Route -->|"Sheet task: Python"| Transform["Restricted workbook transform"]
    Operations --> Validate["Reopen and validate workbook"]
    Transform --> Validate
    Validate --> TaskOutput["Per-task workbook and trace status"]
    TaskOutput --> Batch["Write predictions and validate full batch"]
    Batch --> Metrics["Write run_metrics.json"]
    Batch -->|"predictions and workbooks"| Evaluator["Organiser evaluator with LibreOffice"]
```

ExactSource reads the answer ranges, nearby data, existing formulas and workbook
structure. It de-duplicates cell evidence by worksheet and coordinate and keeps
structural headings before body evidence when a large context must be clipped.
The model returns a JSON plan that must match the route-specific typed schema.
Cell-level tasks can only use built-in operations. Sheet-level tasks may use
either route.

Before publishing a successful candidate, ExactSource checks that it opens and
still contains every answer sheet named by the task. If a task ultimately fails,
ExactSource checks that the initial workbook is readable, writes it to that
task's output path and continues with the batch.

These checks establish the runtime's structural output contract. The organiser's
evaluator separately recalculates the workbook and decides whether its contents
are correct.

Read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for component boundaries,
failure handling, data flow and design trade-offs.

## Outputs and official score

A complete run produces:

```text
out/
  predictions.jsonl
  outputs/<id>.xlsx
  traces/<id>.jsonl
  run_metrics.json
  run.log
```

A full run writes one prediction per dataset task in dataset order. A development
run using `--ids` writes one prediction per selected task, also in dataset order.
Every selected task receives a workbook and a trace file. A task that fails
before its first model request has an empty trace and an error status.

An `ok` status means that ExactSource accepted the plan and reopened the output
workbook successfully. It does not mean that the workbook passed
SpreadsheetBench.

### Check the output structure

This command checks the output layout, workbooks, traces and metrics without
reading golden workbooks:

```sh
uv run --frozen python tools/check_submission.py \
  --dataset-dir /absolute/path/to/dataset \
  --submission-dir /absolute/path/to/out
```

Use this command for a complete run against the supplied `dataset.json`. A
development output created with `--ids` needs a matching subset
`dataset.json`.

### Calculate the official score

Use the organiser's evaluator for the official result. It runs outside the
inference image and recalculates workbooks with headless LibreOffice:

```sh
cd /absolute/path/to/encode-hackathon/research
uv run evaluate.py \
  --dataset-dir /absolute/path/to/dataset \
  --predictions /absolute/path/to/out/predictions.jsonl \
  --all \
  --out /absolute/path/to/ExactSource/results.json
```

Keep the host-level elapsed time with the final result:

```sh
/usr/bin/time -p ./run.sh /absolute/path/to/dataset /absolute/path/to/out
```

`run_metrics.json` records task outcomes, model attempts, retries, repairs, token
usage, character counts and latency. Missing measurements remain unknown rather
than becoming zero. The only exception is Tinker's optional cache counters,
which become zero when the protocol omits them or returns null.
[The architecture document](docs/ARCHITECTURE.md#observability) explains the
metric schema and timing boundary.

## Fixed configuration

Inference settings live in `src/exactsource/config.py`:

| Setting | Value |
| --- | --- |
| Provider | Tinker Anthropic-compatible streaming endpoint |
| Model | `Qwen/Qwen3.8-27B` |
| Temperature | `0` |
| Reasoning | Enabled with the supported Boolean setting |
| Completion limit | `16,000` tokens |
| Transport retries | `2` after the first attempt |
| Semantic repair attempts | `1` |
| Concurrent tasks | `4` |
| Workbook context sent to the model | Up to `48,000` characters |
| Prompt text saved per trace record | Up to `20,000` characters |

The model receives up to 48,000 characters of workbook context. Trace files store
a separately shortened copy of the prompt, limited to 20,000 characters. Model
responses remain untruncated after secret redaction. Accepted plan evidence is
stored without trace truncation.

Built-in operation plans are limited to 128 operations, 250,000 cells per
operation and 500,000 destination writes in total. Judge runs cannot override the
provider or model.

`TINKER_API_KEY` is the only required runtime credential. ExactSource does not
use GCP or Gemini credentials. The optional paid training experiment requires
four explicit checks documented in
[`docs/TINKER_COOKBOOK.md`](docs/TINKER_COOKBOOK.md).

## Local development

ExactSource targets Python 3.11 to 3.13. The core runtime uses `httpx`,
`openpyxl` and `pydantic`. `uv` manages the locked environment, Pytest and Ruff
provide local checks, and Docker packages the judge run.

Run the package without Docker:

```sh
uv sync --frozen --group dev
uv run --frozen exactsource \
  --data-dir /absolute/path/to/dataset \
  --out-dir /absolute/path/to/out
```

For a small development run, add one or more task IDs:

```sh
uv run --frozen exactsource \
  --data-dir /absolute/path/to/dataset \
  --out-dir /absolute/path/to/out \
  --ids 41691
```

The data and output directories must not overlap. A direct CLI run also requires
`TINKER_API_KEY`. View all options with:

```sh
uv run --frozen exactsource --help
```

Run the local checks with:

```sh
uv sync --frozen --group dev
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen pytest
uv run --project training --frozen pytest training/tests
```

These tests cover the input boundary, workbook inspection, plans, formula
screening, restricted transforms, task isolation and submission artefacts. They
do not replace the organiser's workbook evaluation.

GitHub Actions repeats the locked lint, formatting, test and build checks on
Python 3.11–3.13, enforces an 80% branch-coverage floor, tests the isolated
training workspace and smoke-tests the submission image. External actions are
pinned to complete commit SHAs and checkout credentials are not persisted.

## Demo and submission

The submission demo shows a batch run rather than a graphical interface.
[`docs/DEMO.md`](docs/DEMO.md) outlines a three-minute recording using real
workbooks, formula-bar checks, traces and unedited evaluator results.

The public video link, team list and full benchmark result are still pending in
[`SUBMISSION.md`](SUBMISSION.md). Before submission:

- Run all 400 tasks and commit the unedited `results.json`
- Add the confirmed team members and demo link
- Record the exact run command and host-level elapsed time
- Keep any fine-tuning claim separate unless a paid run and reproducible
  checkpoint actually exist

## Known limits

- ExactSource can produce a valid but logically wrong plan. Only held-out
  evaluation can establish spreadsheet correctness.
- The inference image does not recalculate formulas. The organiser's evaluator
  performs that step with LibreOffice.
- `openpyxl` may remove OOXML extensions it does not support, including some
  extended data-validation metadata.
- Built-in operations are confined to declared answer ranges. The runner screens
  Python transforms and applies resource limits, but it does not yet compare
  every cell and OOXML part before and after execution.
- ExactSource records parsing, safety, execution and structural failures that it
  detects. Logical errors and unsupported metadata changes may go undetected.
- Generated Python runs with reduced privileges and resource controls inside the
  submission container. These controls limit access but do not make
  model-generated Python safe for general-purpose use.
- Formula checks reject visible references to external workbooks, legacy
  integrations and external services, malformed structural delimiters and
  explicit references to absent worksheets. They do not prove function
  availability, function arity, dynamic targets or calculated results.
  `INDIRECT(A1)` remains valid when its formula text contains no external target.
  The checks reject generated `HYPERLINK` and `IMAGE` calls. `copy_range` rejects
  OOXML what-if data-table formulas because it cannot relocate them safely.
- Every contributing model call uses `Qwen/Qwen3.8-27B`. No second model acts as
  a router, judge or fallback.

## Documentation

- [System architecture](docs/ARCHITECTURE.md): components, data flow, security
  boundaries and trade-offs
- [Evaluation protocol](docs/EVALUATION.md): scoring, held-out checks and
  experiment discipline
- [Tinker Cookbook path](docs/TINKER_COOKBOOK.md): optional training and its
  paid-run checks
- [Organiser clarifications](docs/ORGANISER_CLARIFICATIONS.md): dated rules and
  unresolved questions
- [Demo plan](docs/DEMO.md): evidence to show in the submission video
- [Training workspace](training/README.md): synthetic cases and offline checks
- [Experiments](experiments/README.md): controls, probes and case-level results
- [Provenance](PROVENANCE.md): upstream revision, checksums and licence boundary

## Support and licence

Open a [GitHub issue](https://github.com/MasteraSnackin/ExactSource/issues) with
the task ID, exact command and a redacted error or trace excerpt. Do not attach
API keys, private workbook data or golden workbooks.

ExactSource code is released under the [MIT licence](LICENSE). SpreadsheetBench
is a separate CC BY-SA 4.0 dataset and is not bundled with this repository.
