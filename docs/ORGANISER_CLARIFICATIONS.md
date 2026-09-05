# Organiser clarifications

This file records research-track answers supplied in the hackathon Discord on
5 September 2026. Discord messages are not part of the versioned organiser
repository, so these statements are kept separate from `PROVENANCE.md` and are
identified as participant-supplied evidence rather than upstream source code.

## Confirmed in the supplied exchange

- The final research submission is restricted to `Qwen/Qwen3.8-27B`.
- There is no stated hard duration limit for the complete Tinker prediction run.
  Accuracy remains the main metric, while method and efficiency, including speed,
  also contribute to judging.
- A prohibited "lookup step" means reading golden output into traces or otherwise
  leaking golden answers. It does not prohibit ordinary internet access.
- Internet access is allowed when required API keys are provided through a clear,
  reproducible run path.
- Deterministic non-model tooling, explicitly including headless LibreOffice
  recalculation, is allowed.
- Tinker does not expose per-user usage data for the hackathon organisation. Teams
  must maintain their own usage evidence.

## ExactSource interpretation

ExactSource takes the conservative interpretation that every model call which
contributes to a submitted workbook must use Qwen3.8-27B. It does not use another
model as a router, judge, verifier, teacher, repair service or fallback. Fixed
local parsing, workbook manipulation, safety checks and LibreOffice evaluation are
deterministic tooling rather than model calls.

Credentials are accepted only through environment variables. Traces record one
ordered entry per provider attempt. `run_metrics.json` recomputes provider-derived
fields from those traces and separately labels coordinator-clock task and batch
timings. It records calls, attempts, provider and plan statuses, known token totals,
missing-usage counts, retry/repair evidence and latency distributions. Monetary
spend is not inferred without an applicable Tinker rate or billing statement.

## Still unconfirmed

The supplied exchange does not answer these questions:

1. May the public 400 golden workbooks be used as disclosed fine-tuning labels, or
   must all 400 remain evaluation-only?
2. Does a fixed `tinker://.../sampler_weights/...` checkpoint trained from
   `Qwen/Qwen3.8-27B` satisfy the Qwen-only requirement without additional model
   identity evidence?
3. Although there is no judging-policy time limit, what infrastructure timeout
   will apply when the organisers execute a submitted container?

Until answered, ExactSource does not use public goldens for training, does not
promote a fine-tuned checkpoint and retains resumable local evidence for long
runs. A statement that no policy limit exists is not treated as proof that the
judging runner has unlimited wall time.
