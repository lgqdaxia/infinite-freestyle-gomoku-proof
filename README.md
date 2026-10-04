# Infinite freestyle Gomoku — complete review materials

**Author:** Gaoqiang Liu, University of Bayreuth, Germany.  
**Contact:** Gaoqiang.Liu@uni-bayreuth.de

The certificate establishes a Black win from the empty infinite integer board
within **35 actual placements by both players**. The rules allow overlines
and have no forbidden moves. Twenty opening representatives cover all 120
normalized first replies; every subsequent White response is checked.

## Papers

- [English review manuscript](papers/revision-en.pdf), [TeX](papers/revision-en.tex): 25 pages.
- [Chinese reading version](papers/revision-zh.pdf), [TeX](papers/revision-zh.tex): 22 pages.
- [Response to the first review](papers/response-to-review.txt).
- [Response to the second review](papers/response-to-second-review.txt).
- Revised-paper supplement: [review-v2-20261004](https://github.com/lgqdaxia/infinite-freestyle-gomoku-proof/releases/tag/review-v2-20261004).
  Its complete certificate remains the unchanged v1 data release linked below.
- [Original dated preprint v1](papers/preprint-v1-en.pdf),
  DOI [10.5281/zenodo.23126820](https://doi.org/10.5281/zenodo.23126820).

## Complete certificate: download and verify

The [versioned full review release](https://github.com/lgqdaxia/infinite-freestyle-gomoku-proof/releases/tag/review-v1-20261004) provides the original empty
cover and **all 1,482,906 selected dependency files**, frozen mathematical
checkers, input manifest, recorded verification and archive checksums.
Original proof bytes and relative paths are preserved. The JSON dependencies
total **48,588,463,288 bytes (45.25 GiB)**; exact compressed sizes and hashes
are listed in the release's `archive-manifest.json`.

Download that manifest, every `gomoku-full-review.tar.gz.NNN` volume,
`unpack-review.py` and `review_transport.py` from the same release. Put them
in one directory. Use **64-bit Windows and Python 3.12 or newer**; only the
standard library is needed. A short new extraction destination is recommended.

```text
python -B unpack-review.py archive-manifest.json --destination C:\gomoku-review
```

Then, from `C:\gomoku-review`, run:

```text
python -B verify-full-review.py --workers 4 --output-dir fresh-check
```

The output directory must be new. Keep assertions enabled: do not use `-O`,
`-OO` or `PYTHONOPTIMIZE`. The entry checks the complete input manifest and
source identities, invokes the frozen mathematical checker, then seals all
proof bytes again. It imports no search engine and uses no historical success
receipt as an acceptance premise.

Require both **actual exit code zero** and `fresh-check/release-acceptance.json`
with status **`VERIFIED_EMPTY_BOARD_REVIEW_RELEASE`**, scope `empty_board`,
20 accepted opening roots, 120 covered first replies and `max_total_plies` 35.
Missing dependencies, changed hashes, nonzero exits or unfinished coverage
are not accepted. The recorded mathematical run took 27,837.450 seconds
with four workers on an i7-12700H, 31.7 GiB RAM, Windows 11 machine.
Allow **90 GiB free disk** as a planning margin for the extracted files,
filesystem overhead, downloaded volumes and new verification receipts.
The [resource profile](audit/resource-profile.md) supplies exact sizes and
recorded large-leaf worker peak working sets (0.407–0.525 GiB), with measurement scope.

## Verification code and rule census

All eight mathematical checker sources in `scripts/` remain byte-for-byte
frozen, with identities in `CHECKER-FREEZE.json`. Shipping entries and archive
tools are separate from mathematical decisions. Focused transport tests:

```text
python -B test_release_tools.py
python -B test_review_entry.py
```

The [rule census](statistics/rule-use-counts.csv) counts all 17 ordinary rules:
12 occur and five have zero uses. Theorem 6.7 is used 971,354 times; Theorem
6.8 is used 64,888 times. Across 20 opening roots the total is 109,364,098
reachable ordinary-node occurrences, not actual moves or distinct positions.
[Census bindings](statistics/certificate-census.json) and the read-only
[counting helper](tools/count_rules.py) make the statistics traceable.
The [receipt-bound inventory source](tools/inventory_closure.py) and
[streaming-parser tests](tools/test_inventory.py) are also supplied as
provenance for the recorded census. These tools count bytes and stored rules;
the mathematical checker decides strategy validity.

## Audit companion and rejection regressions

The [review audit index](audit/review-audit-index.md) maps 15 long-rule and
coverage obligations to exact functions, frozen-source lines and related
regressions. [Machine-readable index](audit/rule-obligation-index.json).
All 19 named small-fixture tests pass:

```text
python -B test_certificate_rejection.py
```

These tests import only frozen kernels and standard-library modules. The
[test receipt](audit/rejection-test-result.json) binds their actual zero exit,
source and output hashes. Complete-certificate acceptance still uses the
full-review entry above. The original paper DOI identifies its original
snapshot; release tags, commits and hashes distinguish the revised paper
and complete certificate. [Version and resource notes](audit/resource-profile.md).

## Small examples

The repository also supplies a self-contained positional sample. It has 3,696
content-addressed objects and 191,787 reachable ordinary-node occurrences.
This smaller sample has positional scope, not empty-board scope:

```text
python -B verify-review.py --sample --workers 1 --output-dir sample-check
```

Require `sample-check/release-acceptance.json` with status
`VERIFIED_RELOCATED_POSITIONAL_SAMPLE` and an actual zero exit.

The [two-remote-component worked example](examples/two-remote-components/)
illustrates the long-rule bound 13 + 2(1 + 1) = 17 further placements, 35 total:

```text
python -B -m scripts.reference_remote_interruption_sequence examples/two-remote-components/two-remote-components.json --output example-check.json
```

Its expected status is `VERIFIED_REMOTE_INTERRUPTION_STATE`, with
`remaining_plies` 17, `latest_win_ply` 35 and two remote components.

## Licensing

Code: **MIT**. Papers and certificate data: **CC BY 4.0**.
See [LICENSES.md](LICENSES.md). Supplied PDFs do not require a TeX installation.
