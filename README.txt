INFINITE FREESTYLE GOMOKU: COMPLETE REVIEW MATERIALS
Author: Gaoqiang Liu, University of Bayreuth
Contact: Gaoqiang.Liu@uni-bayreuth.de

This package contains the complete empty-board certificate dependency closure,
the original empty-cover.json, eight frozen independent checker sources,
all 17 rule-use counts, and the recorded successful local verification.
The original proof bytes, SHA-256 bindings and relative directories are retained.

Platform: 64-bit Windows; Python 3.12 or newer, standard library only.
The recorded manuscript-time machine had an Intel Core i7-12700H, 31.7 GiB
RAM and Windows 11. The recorded mathematical run used four workers and
27,837.450 seconds. Verification receipts and byte audits require additional
time and storage. The certificate dependencies alone occupy 45.25 GiB of
logical JSON data; allow additional space for the compressed download and
new verification receipts. Search engines are unnecessary.

DOWNLOAD AND EXTRACT
Download archive-manifest.json, every gomoku-full-review.tar.gz.NNN volume,
unpack-review.py and review_transport.py from the same GitHub release.
Place them together. From that directory, run:

python -B unpack-review.py archive-manifest.json --destination C:\gomoku-review

The destination must be new. This checks all volume hashes and extracts the
original directory structure. A short destination avoids unnecessary path length.

VERIFY
From C:\gomoku-review, run this single line, preserving the two ASCII hyphens:

python -B verify-full-review.py --workers 4 --output-dir fresh-check

Choose a new output directory on each run. Use ordinary Python with assertions
enabled. The verifier checks the shipped input manifest and frozen source
identities, recomputes all mathematical proof obligations, and checks all input
bytes again. It imports no search code and reuses no historical success receipt.

SUCCESS
Require an actual process exit code of zero and fresh-check/release-acceptance.json
with status VERIFIED_EMPTY_BOARD_REVIEW_RELEASE, scope empty_board, 20 accepted
opening roots, 120 covered normalized first replies, and max_total_plies 35.
The 35 bound counts actual placements by both players from the empty board.
An exception, nonzero exit, missing dependency, changed digest, incomplete
coverage or missing final record is a failed/unfinished verification.

LICENSES
Code: MIT. Manuscripts and certificate data: CC BY 4.0. See the license files.
Repository: https://github.com/lgqdaxia/infinite-freestyle-gomoku-proof
Recorded paper v1 DOI: https://doi.org/10.5281/zenodo.23126820
