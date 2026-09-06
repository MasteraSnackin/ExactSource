# Provenance

ExactSource was developed against the Ylookup organiser repository at commit
[`37d9016264762a25cae49e077cd0893055bd9093`](https://github.com/ylookup/encode-hackathon/tree/37d9016264762a25cae49e077cd0893055bd9093/research),
dated 5 September 2026. The repository's `research/evaluate.py` and `research/sb.py`
at that revision are the scoring authority; they are not copied or modified here.

The public data control used SpreadsheetBench Verified 400 from the organiser's
download script:

- archive URL: `https://huggingface.co/datasets/KAKA22/SpreadsheetBench/resolve/main/spreadsheetbench_verified_400.tar.gz?download=true`;
- organiser-pinned archive SHA-256: `10ef893dd29cb13ab97143ea787e68cdc9574a13873ab9a54e50b31dc03fc949`;
- extracted `dataset.json` SHA-256: `bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7`;
- dataset licence: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

The original dataset archive, golden workbooks and organiser evaluator are not
bundled into the ExactSource image or copied wholesale into this repository.
The final-submission evidence necessarily contains adaptations of the supplied
initial workbooks under `outputs/`, source context in `traces/`, and evaluator
evidence in `results.json`. Those benchmark-derived artefacts are redistributed
under CC BY-SA 4.0 with attribution to SpreadsheetBench and its
[published dataset page](https://huggingface.co/datasets/KAKA22/SpreadsheetBench).
Changes are identified by their location: ExactSource generated the workbook
edits and traces, 31 failed tasks retained safe initial-workbook fallbacks, and
the unchanged organiser evaluator produced `results.json` after LibreOffice
recalculation. The application source code is original work released under the
MIT licence.

Seven evaluated output workbooks retain external-link metadata already present
in their corresponding public initial workbooks: tasks `31746`, `32337`,
`42216`, `50051`, `524-31`, `52575` and `53994`. ExactSource did not introduce
those targets. They include inherited local-path text and public HTTPS targets;
some may be contacted if a spreadsheet client is allowed to update external
links. They are preserved in the scored artefacts rather than silently removed
after evaluation. No target contains the ExactSource host username, audit path
or current Tinker credential. Inspect these untrusted workbooks with external
updates disabled.

Runtime image inputs are pinned by multi-architecture digest in the `Dockerfile`,
and Python dependencies are resolved in `uv.lock`.
