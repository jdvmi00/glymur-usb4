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
and board DTS, then every patch in `patches/series` order. It verifies all 98
final-source hashes and the saved configuration. Output is
`build-output/reconstructed/linux-7.3-rc2/`; an existing destination is refused.
No kernel compilation, installation or hardware access occurs.

The result is the series as of Surface candidate 1.151, not a byte copy of the
tested 1.151 kernel. That kernel also carried board, wireless, GPU and power
changes outside this series (see [the change list](CHANGES-1.151.md)) and no
longer applied baseline patch 0010. Of the 98 files checked, 93 equal their
1.151 versions; the other five also carry those changes in 1.151. The saved
configuration is the 1.73 checkpoint; the tested kernel differed only in the
default CPU frequency governor and three options for the left-out memory
latency driver. A build of the tree therefore reports its own release,
`7.3.0-rc2-1.151-glymur-usb4-ARCH`, rather than the tested kernel's
`7.3.0-rc2-1.151-aarch64-ARCH`. [Results and limits](VALIDATION.md) records
a build of the reconstructed tree.

Tests compile with `tests/harness.h`: failed C assertions retain their stderr
message and exit with status 134 instead of invoking the system crash handler.
The negative controls require that status; setup errors and other exit statuses do
not count as successful rejection. No system crash-reporting settings change.

For another build system, use the same upstream base and baseline preparation
order in `tools/review.py`, then apply the files listed in `patches/series` with
`git apply`. Use `reproduce/kernel.config`, which differs from the tested
configuration only as described above. The generated tree is input to the
builder's existing ARM64 kernel/package process; this repository does not
supply that packaging or firmware. See the
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
