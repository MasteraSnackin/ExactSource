# ExactSource

ExactSource is a formula-aware spreadsheet reasoning system for the Ylookup × Encode Rebuild Private Markets Hackathon research track. It turns a natural-language SpreadsheetBench task and its initial Excel workbook into a completed workbook while preserving formulae, worksheet structure and unrelated cells within the OOXML feature set supported by openpyxl.

The repository is built around the organiser's reproducibility contract: unseen input is read from a read-only `/data` mount and all predictions, workbooks, traces and logs are written to `/out`. It does not read or search for golden workbooks during inference.

No benchmark score is claimed yet. `SUBMISSION.md` deliberately leaves the official 400-task result pending until it has been produced by the shipped evaluator.

An optional isolated SFT scaffold is also present under `training/`. Its 16
hand-authored synthetic cases have been prepared and validated offline as 12
training and 4 tuning examples using the pinned Qwen tokenizer. This did not call
the paid training API, create a checkpoint, change the inference model or run the
full benchmark. See `training/README.md` for the exact evidence boundary and paid
gate.

## Run with Docker

Prerequisites:

- Docker with a running engine;
- a SpreadsheetBench-format dataset directory containing `dataset.json` and the task folders it names;
- a Tinker API key available to the shell as `TINKER_API_KEY`.

Headless LibreOffice is required by the organiser's scoring environment to
recalculate workbooks, but it is deliberately not part of the inference image.
The optional SFT preparation also uses headless LibreOffice to validate
independently specified results for 13 synthetic formula cases. Its other
prerequisite is the pinned `Qwen/Qwen3.8-27B` tokenizer revision already present
in the local Hugging Face cache, so tokenizer loading remains offline.

Set the key through your shell or secret manager, then run. If you used the
git-ignored local `.env` shown by `.env.example`, export its assignments before
starting the child process:

```sh
set -a
. ./.env
set +a
./run.sh /absolute/path/to/dataset /absolute/path/to/out
```

The script builds the `exactsource:local` image and forwards the existing environment variable by name. It does not read a `.env` file or put the key in a Docker build argument. The container itself starts `exactsource` with no arguments and therefore uses the fixed judge paths `/data` and `/out`. Its Python and `uv` images are pinned to multi-architecture manifest digests so the Dockerfile resolves consistently on AMD64 judge machines and Apple-silicon hosts.

The output directory is prepared non-destructively. Files for task IDs in the current dataset are replaced atomically, while unrelated files are retained. A dedicated output directory is still recommended for a clean submission run.

## Output contract

After a complete run, the output directory contains:

```text
out/
  predictions.jsonl
  outputs/<id>.xlsx
  traces/<id>.jsonl
  run_metrics.json
  run.log
```

`predictions.jsonl` has exactly one line per dataset task in dataset order. Each task also has a readable workbook and an ordered trace. If one task fails, ExactSource copies its initial workbook to the expected output path, records the error and continues with the remaining tasks.

`run_metrics.json` schema version 2 is generated atomically after every trace and
workbook has passed structural validation. It retains task, logical-call,
provider-attempt and token totals, and adds latency distributions by task outcome,
provider status and plan status; prompt/response character distributions; semantic
repair counts; transport-retry evidence; and per-task latency values so failures
before a provider call remain auditable. Distributions retain known and unknown
counts and report sum, minimum, exact median, nearest-rank p95 and maximum. Each
token measurement separately records `known_sum`, `known_attempts` and
`unknown_attempts`. A genuinely unavailable trace measurement remains unknown.
Tinker's optional cache-creation and cache-read counters are the one documented
exception: the adapter normalises a missing or null cache counter to zero, while
rejecting an invalid non-null value. The recorded `input_tokens` value already
includes those cache counters; they are shown separately and are not added to that
input total again.

That internal timer starts when task-batch execution begins and stops after final
structural validation; it deliberately excludes dataset loading, solver creation,
metrics publication and Docker build/startup. For the organiser-facing final run,
the file labels wall time and pre-model task timings as coordinator-clock evidence:
they are structurally validated, but cannot be reconstructed from an empty model
trace. Also retain the independent host-level elapsed time reported by:

```sh
/usr/bin/time -p ./run.sh /absolute/path/to/dataset /absolute/path/to/out
```

Validate those structural guarantees without opening any golden workbook:

```sh
uv run python tools/check_submission.py \
  --dataset-dir /absolute/path/to/dataset \
  --submission-dir /absolute/path/to/out
```

The official score must still be produced from the organiser's `research/`
checkout; the evaluator is intentionally not copied into this repository. The
tested organiser revision is
[`37d9016264762a25cae49e077cd0893055bd9093`](https://github.com/ylookup/encode-hackathon/tree/37d9016264762a25cae49e077cd0893055bd9093/research):

```sh
cd /absolute/path/to/encode-hackathon/research
uv run evaluate.py \
  --dataset-dir /absolute/path/to/dataset \
  --predictions /absolute/path/to/out/predictions.jsonl \
  --all \
  --out /absolute/path/to/ExactSource/results.json
```

## Method

ExactSource keeps inference and workbook execution separate:

1. a safe loader resolves only the declared task directory, prompt and single `*init*.xlsx` workbook;
2. a formula-preserving inspector builds a bounded context around the answer
   ranges, existing formula patterns and relevant data, de-duplicating overlapping
   cell evidence by resolved worksheet and coordinate;
3. the fixed model returns a strict, typed solve plan;
4. focused requests use declarative workbook operations such as `set_formula` and relative `fill_formula`;
5. broad sheet-level transformations use a screened, resource-bounded Python workbook transform in an unprivileged child inside the container;
6. the result is validated as a readable workbook before it is atomically promoted.

Every bounded model-sampling attempt, including retryable failures, is retained as exactly one trace record. The resulting workbook-tool input and output are attached to that same record rather than written as extra pseudo-calls. A task that fails before any provider request has an empty trace file and an explicit error status. Workbook-bearing prompts are capped with explicit head-and-tail truncation metadata; model responses and executed plans remain complete for audit. Individual task failure is isolated; malformed datasets and impossible output-contract failures stop the run loudly.

The fixed inference settings are defined in `src/exactsource/config.py`:

- provider: Tinker's Anthropic-compatible streaming endpoint;
- model: `Qwen/Qwen3.8-27B`;
- temperature: `0`;
- reasoning enabled with the model's supported Boolean setting;
- completion ceiling: `16,000` tokens;
- transport retries: `2` after the initial attempt;
- semantic repair attempts: `1`;
- task concurrency: `4`;
- workbook-context budget: `48,000` characters.

Declarative plans are separately limited to 128 operations, 250,000 cells per
operation and 500,000 aggregate destination writes. The public dataset's largest
declared answer footprint is 104,110 cells, so these limits retain more than twice
that observed headroom while preventing an untrusted plan from allocating millions
of openpyxl cells in each worker.

Tinker's current compatible endpoint does not reliably honour forced tool calls for
this model. ExactSource therefore requests one plain JSON object over server-sent
events, keeps the complete raw response in the trace and separates native thinking
and answer blocks structurally. A narrow fallback removes only a leading legacy
text-only reasoning prelude; a literal `</think>` inside returned JSON is preserved.
The answer then passes strict SolvePlan validation and may receive one repair call.
The streamed response avoids relying on one long, silent HTTP response while
retaining a strict final-message check. There is intentionally no provider or model
override, so a judge run cannot silently use a different backend or model.

## Local development

The project targets Python 3.11–3.13 and uses a version-controlled `uv.lock`:

```sh
uv sync --frozen --group dev
uv run pytest
```

Run the package directly against local paths with:

```sh
uv run exactsource \
  --data-dir /absolute/path/to/dataset \
  --out-dir /absolute/path/to/out
```

For a low-cost development smoke test, add `--ids 41691` or a comma-separated
set. The submitted container omits this flag and processes every task.

Design decisions, evaluation discipline, the optional isolated Tinker Cookbook
training path and upstream evidence are documented in `docs/ARCHITECTURE.md`,
`docs/EVALUATION.md`, `docs/TINKER_COOKBOOK.md`,
`docs/ORGANISER_CLARIFICATIONS.md`, `docs/DEMO.md`, `training/README.md` and
`PROVENANCE.md`.

## Limits

- A syntactically valid plan can still encode the wrong spreadsheet logic; only held-out evaluator results establish correctness.
- LibreOffice recalculation is performed by the organiser's evaluator, not claimed from the inference container.
- Workbooks are round-tripped through openpyxl. Unsupported OOXML extensions, including some extended data-validation metadata, may be removed even though supported formulae, worksheet content and unrelated cells are preserved.
- The model may fail on underspecified instructions, unsupported Excel features or transformations that exceed the constrained-runner limits. Such failures are surfaced rather than hidden.
- The generated-code controls are defence in depth inside the submission container, not a general-purpose Python security sandbox.
- Formula screening detects prohibited functions and statically visible external
  references; it is not semantic taint analysis. A legitimate dynamic expression
  such as `INDIRECT(A1)` is allowed when the formula itself contains no external
  target syntax, so workbook data can still determine the reference at calculation
  time. Generated `HYPERLINK` and `IMAGE` calls are rejected entirely.
- The organiser confirmed that model use in the final research submission is
  restricted to `Qwen/Qwen3.8-27B`. ExactSource does not use another model as a
  router, judge or fallback; deterministic workbook tooling remains separate from
  model inference.

ExactSource code is MIT licensed. SpreadsheetBench is a separate CC BY-SA 4.0 dataset and is not bundled into the Docker image.
