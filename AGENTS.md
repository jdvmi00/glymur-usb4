# Source maintenance

Read README.md, CONTRIBUTING.md and docs/PROVENANCE.md before working here.

Preserve the imported source fingerprints and original authorship. An intentional
source change needs an explicit patch, updated derivation record and matching
validation; never refresh hashes merely to make verification pass. Check
upstream overlap before preparing kernel submissions. Keep firmware, private
captures, credentials and build output out of commits.

The tested board is the 13.8-inch, 12-core Mahua Surface Laptop 8. Keep source
checks, builds, simulated tests, hardware operation and installation validation
distinct. Source work must not modify an installed system or boot configuration.
Run `python -B tools/review.py check` after changes and reconstruct/test when
patches or the preparation path change. Publication and hardware changes need
separate authorization from the task owner.
