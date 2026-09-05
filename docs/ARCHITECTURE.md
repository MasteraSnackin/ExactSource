# ExactSource architecture

ExactSource is a spreadsheet transformation agent built for the Ylookup ×
Encode Research Track. Its output is an edited workbook, not a prose answer.
The runtime treats workbook content as untrusted data and never reads a golden
workbook while solving a task.

## Why it is split into two routes

The public SpreadsheetBench Verified set contains two materially different
problems. Nearly every cell-level task expects formulas, while sheet-level
tasks are mostly procedural operations such as filtering, deleting,
deduplicating, sorting and merging. Asking one model response to enumerate the
final value of every answer cell is both lossy and expensive: some answer
ranges exceed 100,000 cells even when only a few cells actually change.

ExactSource therefore uses this flow:

```text
dataset task and initial workbook
              |
              v
formula-preserving, target-aware context builder
              |
       +------+------+
       |             |
       v             v
cell-level       sheet-level
compact patch    bounded transform
       |             |
       +------+------+
              |
              v
validate, save, reopen and record trace
              |
              v
workbook + prediction + trace under /out
              |
              v
validate all tasks + derive run_metrics.json
```

The formula route can write literal values or formulas, translate one anchor
formula across a range, clear a range, or copy a range. The transformation
route runs a screened `transform(wb)` function in a separate child process
with a stripped environment, explicit helper allow-lists, resource limits, no
child-process allowance and a fixed input/output path. When the container starts
as root, the generated-code child drops to an unprivileged identity before Python
starts. This is defence in depth inside the required container, not a claim that
Python syntax screening is an independent security boundary.
An individual failure falls back to an untouched copy of the initial workbook
so every task remains gradeable.

## Trust boundaries

- `/data` is resolved once and treated as read-only.
- Dataset paths must remain beneath `/data`, including after symlink
  resolution.
- Golden filenames are neither searched for nor opened by inference code.
- The model identifier, temperature, timeouts and retry limits are fixed in
  source.
- Provider credentials are read only from the documented environment variable
  and are redacted from errors.
- Model-written code receives no provider credential and cannot select files.
- Plan operations are validated against existing worksheet names and valid
  spreadsheet coordinates before mutation.
- Declarative plans are preflighted before workbook loading and capped at 128
  operations, 250,000 cells per operation and 500,000 aggregate writes.
- Newly introduced formulae are rejected when their formula text contains a
  prohibited external-service, external-workbook or legacy DDE/integration
  capability. Generated `HYPERLINK` and `IMAGE` calls are rejected entirely.
  Identical pre-existing formulae are preserved rather than silently deleted.
  This is static capability screening, not data-flow proof: `INDIRECT(A1)` remains
  valid when no external target syntax appears in the formula text.
- Workbooks are written to temporary files on the output filesystem, reopened,
  and atomically moved into place.
- Trace-derived aggregates and separately labelled coordinator-clock timings are
  published only after every task artefact validates, then written atomically at
  `/out/run_metrics.json`.

## Context construction

The context builder loads formulas rather than cached values alone. It records
worksheet dimensions and sparse non-empty cells. Cell evidence is keyed by the
resolved worksheet, row and column, then emitted once in this priority order:

1. answer ranges and their neighbouring rows and columns;
2. data ranges supplied by task metadata;
3. workbook-wide formula patterns;
4. remaining populated cells.

Workbook tables, defined names, merged cells and used-range summaries are retained
as separate structural evidence. Identical A1 addresses on different worksheets
remain distinct. Ordinary blank neighbours are omitted, while explicit blank
answer cells and styled blanks are retained.

Truncation is explicit. The trace records the original character count, the
retained count and a SHA-256 digest so prompt construction can be audited
without embedding an entire large workbook in auxiliary metadata.

## Reproducibility

Runtime configuration lives in `src/exactsource/config.py`. Every bounded
provider sampling attempt is written as one line in the task's JSONL trace with the fixed
model name, temperature, prompt, returned content, token counts, latency and
any redacted error. Tool input and output are attached to the corresponding
model-call line. Workbook-bearing prompts may be truncated with a recorded digest,
but the response and executed plan remain complete. A pre-call failure produces an empty trace and an error-status
prediction rather than a fabricated model-call record. Transport retries and the
optional semantic repair are bounded. No evaluator mismatch or golden value may
enter a repair prompt.

The production provider is Tinker's Anthropic-compatible streaming endpoint with the exact
`Qwen/Qwen3.8-27B` model identifier. A live compatibility probe established that
ordinary completions work but required tool calls are not reliable for this model.
The adapter therefore consumes the server-sent event stream, retains the raw text,
and separates native thinking blocks from answer text using the streamed block
types. A narrow compatibility fallback removes only a leading legacy text-only
reasoning prelude; it preserves a literal `</think>` after the JSON answer has
begun. Strict parsing then relies on the typed plan validator plus one bounded
repair call.

## Run evidence

Task workers never share mutable usage counters. Once they finish, the coordinator
reads their final JSONL traces in dataset order and publishes schema-version-2
`run_metrics.json`. It records the wall time from batch execution start through
output validation; task totals; logical model calls grouped by task and semantic
attempt; provider-attempt totals; provider and plan outcomes; semantic repairs;
transport retries; trace-derived usage; character volumes; and task, call,
provider and pipeline-stage latency distributions. Each distribution exposes
known and unknown counts, sum, minimum, exact median, nearest-rank p95 and maximum.
The metrics file also retains the latency keyed by task ID. Values are cross-checked
against terminal traces where they exist, while pre-model task failures still
contribute timing evidence even though their trace is correctly empty.

Every usage measurement contains `known_sum`, `known_attempts` and
`unknown_attempts`. Missing and explicit-null trace values increase the unknown
count instead of being treated as zero. Tinker's optional cache-creation and
cache-read counters are normalised by the adapter to zero when the protocol omits
them or returns null; invalid non-null counters are rejected. `input_tokens` is
already the adapter's total input count including cached input, so the two cache
fields are reported independently and never added to it. The structural submission
checker recomputes trace-derived fields and rejects missing, malformed or
inconsistent metrics. It validates the shape and internal consistency of
coordinator-clock wall time and pre-model task timings, but cannot independently
reconstruct those values from model traces; the separate host-level `/usr/bin/time`
record is the external full-run timing evidence.
