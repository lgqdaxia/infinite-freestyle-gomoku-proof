# Verification resources and version identities

## Actual data sizes

- Complete download: **1,776,528,706 bytes** (1.78 decimal GB).
- Selected certificate dependency JSON: **48,588,463,288 bytes** (45.25 GiB).
- Full uncompressed archive payload, including metadata: **48,995,985,879 bytes**.
- Archive entries: **1,482,929**. Filesystem allocation and directory metadata are additional.
- Suggested free disk space: **90 GiB**. This is a planning margin, not a measured requirement.
  Use a short new extraction destination; retain room for new verification receipts.

## Recorded memory measurements

The preserved Windows four-worker probe checked four actual large ordinary leaves,
with zero worker exits and no historical receipt reuse. Per-process peak working
sets were 540,823,552; 436,477,952; 563,286,016; and 510,001,152 bytes
(**0.407–0.525 GiB**). Their separate peaks sum to 2,050,588,672 bytes (1.91 GiB).
That sum is neither a sampled simultaneous maximum nor a bound for a whole cover run.
The recorded reference machine had 31.7 GiB RAM. [Raw probe](recorded-four-worker-resource-probe.json)
and [machine-readable resource profile](resource-profile.json) retain measurement scope and hashes.

## Persistent identities

The original manuscript has version DOI
[10.5281/zenodo.23126820](https://doi.org/10.5281/zenodo.23126820)
and concept DOI [10.5281/zenodo.23126819](https://doi.org/10.5281/zenodo.23126819).
Those identify the original paper, not this revised paper or the complete certificate.
The complete certificate is preserved in the versioned
[review-v1-20261004 release](https://github.com/lgqdaxia/infinite-freestyle-gomoku-proof/releases/tag/review-v1-20261004),
source commit `5e7c5d769a8ff4743fe4a8ecbc381fd4a2b6d2fb`.
Its archive SHA-256 is
`d003eb5d1372d80c1d92da3a4bd225d8d8c140d06c53fd9e03aa48f1f808ed33`.
The revised paper and audit indexes use a separate versioned release and source commit;
the original archive and its input byte identities remain unchanged.

A preservation service such as Zenodo can additionally deposit the existing volumes,
frozen-source snapshot, revised paper and manifests under a new linked DOI. That DOI
should describe this exact combined version; the original paper DOI must not be
presented as the identifier of the certificate corpus. The present publication is
identified by its versioned GitHub release, commit and file hashes.
