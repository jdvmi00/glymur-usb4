# Authorship and source identity

`IMPORT-MANIFEST.json` maps each retained input to its original allowlisted
path and SHA256 from source commit
`5a1b08350e42f45f83e32cdf07ace463f6cace0b`. Entries in `files` are unchanged;
the adapted tests in `derived_files` retain both their original and current
hashes and a description of the harness-only change.
`provenance/derivation.json` records the original inputs, the pinned aggregate
patch and its partition into nine review patches. Every file's diff stays
together, with every original hunk preserved. Only grouping, descriptive headers
and diff path prefixes change; the resulting C and device-tree bytes do not.

- `provenance/usb4/` preserves Konrad Dybcio's USB4 PHY v5 series and the
  subsequent PHY, clock/reset, GLINK and host-router decomposition.
- `provenance/display/` preserves the original quad-pipe patch and DSC/FEC deltas.
- `reproduce/baseline/` retains the original board/distribution patch headers.

Provenance patches overlap the review series. Keep them for attribution and
review; do not apply them again during reconstruction. Each review patch names
its retained source attribution. Local diffs do not always identify per-hunk
authors; the series does not invent those credits or new sign-offs. Its
committer is not the author of every included change.

Original SPDX identifiers, authors, sign-offs and license notices remain
applicable. See [licenses](../LICENSE.md) for the helper, tests, documentation
and imported-source terms. Complete Linux licensing files are available in the
reconstructed upstream tree.

Some register values and protocol behavior came from hardware and Windows driver
investigation. Firmware, proprietary driver binaries and private investigation
records are excluded. No ownership of third-party work or upstream acceptance
is claimed. The retained upstream patch series is a record of dependencies,
not a claim about what is currently merged; check current maintainer trees
before porting or submitting changes.

The public source snapshot is based on the reviewed revision
`beb46edc9ed52b23ea68634e3ae90fe2cd15106b`. That revision corrected dependency
descriptions without changing kernel hunks. The source fingerprints remain
the original 1.85 values. Publication cleanup changes documentation, adds
license texts and makes intentional assertion failures exit without system
crash notifications. This harness adjustment does not change the extracted
kernel functions or test scenarios. Earlier development commits are not needed
to apply or verify the published series.
