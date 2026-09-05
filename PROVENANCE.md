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
- dataset licence: CC BY-SA 4.0.

The dataset and organiser evaluator are not bundled into the ExactSource image.
The application code in this repository is original work released under the MIT
licence. Runtime image inputs are pinned by multi-architecture digest in the
`Dockerfile`, and Python dependencies are resolved in `uv.lock`.
