# Experiment register

## Final public 400-task run

`full_400_8b84dba.json` is the sanitised record of one uninterrupted run over
all 400 supplied public benchmark tasks. The unchanged organiser evaluator
graded all 400 outputs with no missing items and no evaluator errors:

| Metric | Result |
|---|---:|
| Pass rate | 0.7550 (302 / 400) |
| Cell accuracy | 0.8006 (238,486 / 297,882) |
| Cell-level pass rate | 0.7818 |
| Sheet-level pass rate | 0.6960 |

The solver completed 369 tasks through its normal execution path and emitted a
safe fallback for 31 tasks. These are runtime outcomes, not correctness labels:
the evaluator, independently, found 302 exact task passes. The run made 498
model calls and wrote 498 trace records. Ninety-eight tasks received one second
call: 72 max-token recoveries and 26 ordinary repairs. There were no transport
retries.

Host wall time was 23,983.52 seconds (6 hours, 39 minutes, 43.52 seconds); the
separate evaluator run took 329.66 seconds. The provider reported 5,592,930
output tokens. It reported zero input tokens, but this is recorded as unavailable
rather than interpreted as zero input usage. No monetary-cost estimate is made.

The public record identifies solver commit
`8b84dba1d9263e2123b8f15267239b70ff817907`, the exact dataset and evaluator
hashes, evaluator commit, LibreOffice 26.8.0.3, and the Linux/ARM64 container
image ID. The complete local run directory was approximately 36 MB and its
largest file was below 1 MB. Both the generic secret-pattern scan and the exact
credential-value scan passed. The record also pins SHA-256 values for
`predictions.jsonl`, `run.log`, `run_metrics.json` and the unedited
`results.json`.

The sanitised experiment JSON excludes raw traces, model prompts and responses,
workbook contents, credentials and the raw evaluator result. It retains only
aggregate evidence and, per item, `id`, `type`, `status`, `pass`, `correct`,
`cells` and `mismatch_count`. A mismatch count is the number of sanitised
mismatch records present, not a replacement for `cells - correct`.

The separate organiser-required full-run artefacts are published at repository
root: `results.json`, `traces/` (including the model prompts and responses) and
the output workbooks under `outputs/`. The current-key scan found no match in
publishable repository files, existing commits or completed run artefacts,
including decompressed workbook payloads. A generic-pattern scan found no
credential candidate in the completed run artefacts. Ignored local secret files
were outside that publication scan.

## Predeclared ten-task acceptance run

`acceptance_10_8b84dba.json` records the acceptance gate run immediately before
the full benchmark. Its ten development IDs were declared in advance and split
evenly between cell-level and sheet-level tasks. All ten completed through the
normal runtime path in 601.15 seconds, producing ten model calls and ten trace
records with no repair call or fallback.

| Metric | Result |
|---|---:|
| Pass rate | 0.9000 (9 / 10) |
| Cell accuracy | 0.9987 (776 / 777) |
| Cell-level pass rate | 0.8000 |
| Sheet-level pass rate | 1.0000 |
| Missing / evaluator errors | 0 / 0 |

The provider reported 117,592 output tokens. As in the full run, its reported
zero input-token value is treated as unavailable, and no monetary-cost estimate
is made. This acceptance gate demonstrates both execution routes on a small,
predeclared set; it is not presented as a representative benchmark estimate.
Its JSON follows the same sanitised-record boundary described above.

## Public split v1

`public_split_v1.json` freezes a deterministic metadata-stratified split before
model-result tuning:

- 320 development tasks: 220 cell-level and 100 sheet-level;
- 80 hold-out tasks: 55 cell-level and 25 sheet-level;
- split seed: `exactsource-public-v1`;
- public `dataset.json` SHA-256: `bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7`.

The split generator reads task metadata and initial workbooks only. It does not
open golden workbooks. Re-running `tools/freeze_split.py` with the recorded seed
produces a byte-identical file.

## Untouched-workbook control

`copy_baseline_dev_results.json` is the unmodified organiser evaluator output for
the untouched-workbook control on the 320 development IDs. It is not a final
400-task submission score.

| Metric | Result |
|---|---:|
| Items / graded | 320 / 320 |
| Missing / errors | 0 / 0 |
| Pass rate | 0.0063 |
| Cell accuracy | 0.3510 |
| Cell-level pass rate | 0.0045 |
| Sheet-level pass rate | 0.0100 |

The control artefacts were generated with `tools/make_copy_baseline.py`, then
scored with the organiser's unchanged `research/evaluate.py` at commit
`37d9016264762a25cae49e077cd0893055bd9093` and LibreOffice 26.8.0.3. The 80
hold-out IDs were excluded from the evaluator command and remain unscored.

## Development prompt profile

`prompt_profile_dev.json` records the original input-only request-size baseline
for the frozen 320-task development split.
`prompt_profile_dev_route_schema_v1.json` records the same tasks after two
deterministic prompt changes: cell tasks omit the unusable Python-route manual,
and the model-facing schema omits presentation-only titles and redundant
discriminator mappings while retaining its validation constraints. The compact
schema is placed in the stable system prefix rather than escaped inside the user
payload. `prompt_profile_dev_context_dedup_v1.json` adds workbook-qualified cell
evidence de-duplication: answer-target evidence wins over declared source regions,
formula catalogues and general populated-cell samples, while same-coordinate cells
on different worksheets remain distinct. Ordinary blank neighbours are omitted;
explicit target blanks and styled blanks remain. It also removes task metadata that
was duplicated inside the workbook context and allocates a tight context budget by
structural child block, retaining range and worksheet headings before their bodies.
The report records the distinct cell and sheet schema sizes and hashes rather than
presenting the sheet schema as universal.

`prompt_profile_dev_context_dedup_tokens_v1.json` profiles that same final prompt
again through the exact pinned `Qwen/Qwen3.8-27B` tokenizer and
`qwen3_8_xhigh_reasoning` renderer. The character measurements in both final
reports are identical.

The profiler uses the production context and message builders, opens only initial
workbooks, makes no provider request and does not open any golden workbook. The
per-task records contain lengths and task IDs, not cell contents or prompts.

The current profiles report:

| Measure | Original | Route/schema v1 | Final with de-duplication | Final versus original |
|---|---:|---:|---:|---:|
| Development tasks | 320 | 320 | 320 | none |
| Cell / sheet tasks | 220 / 100 | 220 / 100 | 220 / 100 | none |
| Truncated contexts | 6 (1.875%) | 6 (1.875%) | 3 (0.9375%) | -3 tasks |
| Median emitted context characters | 7,225 | 7,225 | 4,066 | -43.72% |
| Model-visible content, mean characters | 21,751.69 | 19,756.19 | 15,537.98 | -28.57% |
| Model-visible content, median characters | 17,522 | 15,507 | 11,798 | -32.67% |
| Model-visible content, p95 characters | 49,056 | 46,618 | 35,957 | -26.70% |
| Model-facing cell schema characters | 3,743 | 2,720 | 2,649 | -29.23% |
| Model-facing sheet schema characters | 3,743 | 2,720 | 3,052 | -18.46% |

For the final prompt only, the exact generation-prompt input-token distribution is:

| Measure | Tokens |
|---|---:|
| Mean | 5,735.11 |
| Median | 3,785 |
| p95 | 14,357 |
| Maximum | 29,853 |

Reproduce it against a local copy of the public dataset:

```sh
uv run --frozen python tools/profile_prompts.py \
  --dataset-dir /absolute/path/to/dataset \
  --selection-file experiments/public_split_v1.json \
  --selection-field development_ids \
  --out experiments/prompt_profile_dev_context_dedup_v1.json
```

Reproduce the renderer-token report with the isolated locked training environment:

```sh
uv run --project training --frozen python tools/profile_prompts.py \
  --dataset-dir /absolute/path/to/dataset \
  --selection-file experiments/public_split_v1.json \
  --selection-field development_ids \
  --renderer-token-counts \
  --out experiments/prompt_profile_dev_context_dedup_tokens_v1.json
```

Schema-version-3 prompt reports derive `request_chars` from the same pure fixed
Anthropic-payload serialiser used by the runtime; the two older schema-version-1
reports measured their compact message-list envelope instead. The comparison table
therefore uses model-visible message content rather than mixing those request
envelopes. The token report measures the rendered generation prompt before model output. It
does not retroactively establish an exact token reduction against the earlier
character-only profiles. Provider-reported token usage from completed calls remains
authoritative live-run evidence. These profiles prove that the textual request is
smaller; whether that improves runtime or workbook accuracy still requires a
controlled development-set model ablation.

## Synthetic SFT preflight

`sft_preflight_v1.json` records the offline preparation and default paid-pilot
preflight for `training/cases/synthetic_v1.json`. The 16 cases are independently
authored and contain no benchmark workbook or golden output. All labelled plans
were executed through the production path, every cell outside the answer ranges
was compared with the source, and the 13 formula cases matched separately stated
values after headless LibreOffice recalculation.

The exact Qwen renderer produced examples ranging from 1,779 to 2,385 tokens. The
default four-step pilot would use 8 seeded training examples and two loss-only
passes over the 4 tune examples, for 31,351 model-input tokens against a hard
50,000-token ceiling. This is a preflight measurement, not a training result: no
paid call, checkpoint or benchmark score exists.

## Formula storage-name compatibility

`formula_compatibility.json` is a synthetic engine-compatibility check for the
16 modern-function storage names emitted by ExactSource. The harness creates one
temporary workbook per function, asks the specified LibreOffice executable to
recalculate them, reads the saved cached values, and compares them with fixed
expected values. It does not read any benchmark workbook or golden answer, and
it removes all temporary workbooks after the run.

Run it with an explicit engine path:

```sh
uv run python tools/check_formula_compatibility.py \
  --soffice /Applications/LibreOffice.app/Contents/MacOS/soffice \
  --out experiments/formula_compatibility.json
```

The command prints the same deterministic JSON written by `--out`. It exits 0
only when all cases match, 1 for formula-result mismatches, and 2 when the check
cannot run. The recorded local run passed 16/16 cases with LibreOffice 26.8.0.3.
This verifies these exact synthetic formula shapes on that engine; it is not a
benchmark score or a claim that every use of those functions is compatible.

## Tinker integration smoke test

`tinker_stream_probe_v2.json` records the post-rotation credential check. One
minimal, non-training request reached the exact `Qwen/Qwen3.8-27B` model through
the compatible streaming endpoint and completed in one attempt with HTTP 200,
`end_turn`, 28 provider-reported output tokens and 1,455 ms latency. Reasoning was
disabled, output was capped at 64 tokens and transport retries were disabled to
bound this credential test. The key, prompt and response text are not retained.
This proves authentication and streaming compatibility only; it is not a
production-prompt, accuracy, throughput or checkpoint result.

`tinker_provider_probe.json` records the non-secret compatibility result that led
to the provider design: authentication and plain requests work for the exact model,
whereas two required-tool probes returned the same provider-side no-tool-call
failure. No API key or response text is stored in that file.

`tinker_smoke_41691_result.json` records the official evaluation of one simple
development task after the live Tinker integration check. The fixed
`Qwen/Qwen3.8-27B` model produced
`=VLOOKUP(A7,A1:B5,2,FALSE)` in the required cell. The complete pipeline finished
without fallback, emitted one trace line for one model request, contained no
credential in that trace, and scored 1/1 cells (`pass_rate: 1.0`). This is an
integration check, not evidence of aggregate benchmark performance.

`tinker_stream_probe.json` records a later credential and transport check without
storing the key, response text or reasoning. The exact model completed a minimal
server-sent-events request with HTTP 200 and a clean end-of-turn. The same key was
also accepted by the native SDK's identity layer, but native sampling-session
creation was rejected because the account's default project is read-only and no
writable `TINKER_PROJECT_ID` was configured. The compatible streaming route is
therefore the tested production route for this submission unless the organisers
provide a writable project identifier.

The same streaming implementation then completed development task `56563` in one
provider attempt and wrote an error-aware `SUMPRODUCT` formula. The organiser's
unchanged evaluator recalculated the workbook with LibreOffice 26.8.0.3 and scored
the one graded cell correctly. The unedited evaluator output is retained as
`tinker_stream_smoke_56563_result.json`. This proves the repaired transport and
end-to-end execution path for that case only; it is not an aggregate score.

A second one-attempt smoke run used development task `51-12`, a VBA-style stateful
counting request routed through the restricted Python transform. The response used
11,573 output tokens, completed beyond the former silent 60-second boundary, wrote
the value `4`, and scored the one sheet-level cell correctly after official
LibreOffice recalculation. Its evaluator output is retained as
`tinker_stream_smoke_51-12_result.json`. Together the two smoke cases cover both
execution routes, but they remain integration evidence rather than a benchmark
performance estimate.

`tinker_nonstream_batch_probe.json` records the failure that prompted the
transport change. Six development tasks made 18 bounded non-streaming attempts;
every connection closed without a response at approximately 60 seconds, and every
task correctly received the safe workbook fallback. The timing is evidence of a
silent-response boundary, not proof of which upstream component imposed it. No
hold-out task, golden workbook, key, prompt or model response is included.
