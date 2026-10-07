# Contributing

Start with the [series map](patches/README.md) and [known limits](docs/VALIDATION.md).
Use a focused change with the affected component, concrete failure and expected
behavior. Include the source revision, board, kernel configuration and commands
used to validate it. Strip personal information and credentials from logs.

Run `python -B tools/review.py check`. For patch or reconstruction changes,
[reconstruct and test](docs/REPRODUCE.md) the resulting source. Report build,
simulated-test and hardware results separately; a passing source test does not
establish hardware support. Retain the original source attribution and explain
any deliberate changes to fingerprints in the same contribution.

The host and display pieces are coupled. In particular, the driver
registration in patch 03 references the Qualcomm frontend in 05 when enabled,
05–07 share a display interface, and the sleep support in 16 relies on 10–12,
14 and 15 at runtime. Do not assume a partial series builds independently.
Other boards require their own descriptions and tests. Patches 12 and 13 fix
stock code and do not depend on the rest.

For Linux submissions, first check overlap with current maintainer trees,
preserve the original contributors' authorship, and split remaining changes into
focused commits with verified dependencies and intermediate builds. This
experimental series is not represented as an upstream-ready submission.
