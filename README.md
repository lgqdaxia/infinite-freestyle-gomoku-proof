# Infinite freestyle Gomoku — manuscripts and verification sample

**This directory does not contain the complete empty-board certificate.** It
contains frozen independent checkers, manuscripts, one self-contained
positional sample, and a small worked illustration. A positional sample is not
additional opening coverage and cannot establish the empty-board theorem.

## Manuscripts and current review status

- [Public English preprint v1](papers/preprint-v1-en.pdf), with
  [TeX source](papers/preprint-v1-en.tex): the original dated Zenodo version,
  DOI [10.5281/zenodo.23126820](https://doi.org/10.5281/zenodo.23126820).
- [English major-revision draft](papers/revision-en.pdf), with
  [TeX source](papers/revision-en.tex): 25 pages.
- [Chinese major-revision draft](papers/revision-zh.pdf), with
  [TeX source](papers/revision-zh.tex): 22 pages.
- [Response to the review](papers/response-to-review.txt).

The revised drafts are not a revised Zenodo deposit or an accepted journal
article. The full-corpus rule-use counts are still pending in the drafts.
Complete artifact delivery and a full replay in an environment without access
to the original workspace are also pending. Historical local acceptance
records do not replace that replay. No formalization claim is made.

## Run the self-contained positional sample

Python 3.12 or newer is the proposed runtime; the actual staging test uses
CPython 3.12.14. Only the Python standard library is required for checking.
No search engine, search database, original workspace, or old success receipt
is needed. Use an ordinary interpreter with assertions enabled; **never** use
`-O`, `-OO`, or `PYTHONOPTIMIZE`.

From this directory, run this single copyable command:

```text
python -B verify-review.py --sample --workers 1 --output-dir fresh-check
```

Choose a new output directory for every run. `fresh-check` must not exist.
The expected final file `fresh-check/release-acceptance.json` has status
`VERIFIED_RELOCATED_POSITIONAL_SAMPLE` and scope
`positional_only_not_empty_board`. Both a zero exit status and that exact
acceptance record are required. Any exception, nonzero exit, missing record,
or altered byte manifest is failure/unknown, never an accepted proof. Running
without `--sample` is deliberately rejected because the full empty-board
corpus is absent. The sample comprises 3,696 content-addressed objects (3,682
ordinary proofs and 14 bundles) and 191,787 reachable ordinary-node occurrences.

The eight mathematical kernel files are unchanged and separately identified
in `CHECKER-FREEZE.json`. `reference_gap_package.py` is the content-addressed
package adapter; `verify-review.py` and `receipt_stream.py` handle shipping and
receipts. `release.json` binds the sample payload to `shipped-manifest.jsonl`.
`STAGING-MANIFEST.json` records the rest of this small repository's bytes.

## Two remote components: worked illustration

The example is a normalized 18-stone position, not an empty-board proof and not
a new opening root. It demonstrates local responses and two remote interruption
graphs, with the bound 13 + 2(1 + 1) = 17 further actual placements, 35 total.
Recheck it directly using the frozen independent checker:

```text
python -B -m scripts.reference_remote_interruption_sequence examples/two-remote-components/two-remote-components.json --output example-check.json
```

Expected status: `VERIFIED_REMOTE_INTERRUPTION_STATE`, `remaining_plies` 17,
`latest_win_ply` 35, and two remote components. The supplied historical
verification and recorded states are supporting information, not acceptance
premises for the fresh check. This command requires no primary search code.

## Full proof release plan

The complete selected dependency closure is being inventoried. When the full
package, licenses, file manifests, storage requirements, and fresh isolated
full mathematical replay are complete, publish the full compressed certificate
as versioned GitHub Release assets (split into volumes if required), together
with its exact command and successful acceptance record. Do not place search
caches, engine binaries, or the million-file working corpus into ordinary Git.
No full-release size or external-replay completion is asserted here.

Checking the proof does not require compiling the manuscripts. English TeX
uses standard LaTeX packages; the Chinese source additionally uses XeLaTeX and
the named Windows fonts (Times New Roman, SimSun, SimHei). The PDFs are supplied
so reviewers do not need those compilation dependencies.

See [LICENSES.md](LICENSES.md) for the distinct manuscript/code/data scopes.
