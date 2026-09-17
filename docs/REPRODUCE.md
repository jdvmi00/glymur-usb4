# Reconstruct and test

Requires Python 3.12+, Git and about 3 GB free space; tests also require a C
compiler with ASan/UBSan. From the repository root:

```sh
python -B tools/review.py check
mkdir -p build-output/cache
curl --fail --location --output build-output/cache/linux-7.3-rc2.tar.gz \
  https://git.kernel.org/torvalds/t/linux-7.3-rc2.tar.gz
python -B tools/review.py reconstruct --archive build-output/cache/linux-7.3-rc2.tar.gz
python -B tools/review.py test
```

The helper checks the archive hash, applies the 39 preserved baseline patches
and board DTS, then every patch in `patches/series` order. It verifies all 93 final-source
hashes and the saved configuration. Output is
`build-output/reconstructed/linux-7.3-rc2/`; an existing destination is refused.
No kernel compilation, installation or hardware access occurs.

Tests compile with `tests/harness.h`: failed C assertions retain their stderr
message and exit with status 134 instead of invoking the system crash handler.
The negative controls require that status; setup errors and other exit statuses do
not count as successful rejection. No system crash-reporting settings change.

For another build system, use the same upstream base and baseline preparation
order in `tools/review.py`, then apply the files listed in `patches/series` with
`git apply`. Use `reproduce/kernel.config` for the exact Surface configuration.
The generated tree is input to the builder's existing ARM64 kernel/package
process; this repository does not supply that packaging or firmware. See the
[series map](../patches/README.md) for dependencies and configuration guidance.
Other kernel bases or selected subsets require a separate port and validation.

The baseline patches include inherited audio, Wi-Fi and distribution changes.
They are required to recreate the tested board source; removing them would
change the comparison base. Their original bytes and author headers remain.
The packaging recipes, installation records and intermediate experiments are
not needed for this source reconstruction and are omitted.

The upstream Linux 7.3-rc2 archive SHA256 is
`6b97fb9397172e95ed95b56a78524a184bf186858bea7a271b9ebe81a0e57417`.
The helper creates isolated Git metadata in the reconstructed tree so outer
workspace ignore rules cannot cause patches to be silently skipped.
