# Authorship and source identity

`IMPORT-MANIFEST.json` maps each retained input to its original allowlisted
path and SHA256 in the Surface Laptop 8 project. Entries in `files` are
unchanged copies from source commit `916fea4551f656c35f3fdaec1ad1c5a4ecf885b3`
(the manifest's `source_commit`). Entries in `derived_files` are the review
patches, the
source fingerprint list and the tests; each records its source, where there
is one, and the change made. `provenance/derivation.json` records the
original inputs, the pinned aggregate patch and its partition into nine
review patches, and the 1.89 and 1.151 updates (`update_1_89`,
`update_1_151`). Every file's diff stays together within patches 01-09, and
within patches 10-16. Only grouping, descriptive headers and diff path
prefixes differ from the recorded Surface sources; the resulting C and
device-tree bytes do not.

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

The public source snapshot was based on the reviewed 1.85 revision
`beb46edc9ed52b23ea68634e3ae90fe2cd15106b`; the 1.89 update regenerated
seven file diffs in patches 01, 05 and 07. Publication cleanup changed
documentation, added license texts and made intentional assertion failures
exit without system crash notifications, without changing the extracted
kernel functions or test scenarios.

## 1.151 update

The update brings the series to the kernel installed on the tested Surface
since 5 October 2026. Its inputs are the candidate diffs 1.90-1.151 at Surface
commit `87d851a6891772d7ed15a08e0449b77a12a78356`. Assembling 1.151 from its
committed recipe inputs matched all 150 recorded fingerprints and all 95,967
source files of the build tree its packages came from.
[The change list](CHANGES-1.151.md) shows each candidate and whether it is in
the series.

Patches 01-09 end at the in-scope state of candidate 1.130; patches 10-16 add
1.131-1.151. Each file section is
`git diff --full-index --diff-algorithm=histogram` from the previous state,
with `a/` `b/` prefixes and the kernel's `.gitattributes` diff drivers
disabled. The same command reproduces all 93 sections of the 1.89 patches
byte for byte; 60 of them are unchanged. Four files the 1.89 series changed
(`tb.h`, `usb4.c`, `xhci.c`, `usb/quirks.h`) are back to stock and leave it;
`tb.c` leaves patch 03 and returns in 12. Five files join it: the DWC3
`core.c`, `dwc3-qcom.c` and `glue.h`, and MSM `msm_atomic.c` and `msm_kms.c`.

`reproduce/expected-source.sha256` is now derived rather than copied: the
lines of the 1.151 manifest for the 98 files the 1.89 or 1.151 series
touches, in the same order, with the series result recorded for the five
files that also carry left-out 1.151 changes. 93 lines are unchanged from the
1.151 manifest. The baseline still applies patch 0010 (Surface DP AUX
backlight mode) although 1.113 and later do not; its replacement, a PWM
backlight, is outside this series.

The Surface kernel also carries other contributors' work that this
repository does not include, among it Akhil P Oommen's GMU series, Manivannan
Sadhasivam's hci_qca patch, Qualcomm's SCMI memory-latency series and Krishna
Kurapati's eUSB2 repeater fix. The changes this update adds are local Surface
work. Patch 12 changes upstream code by Mika Westerberg and patch 13 upstream
code from Krishna Kurapati's role-switching series; neither change is posted.
The sleep register sequence in patches 10 and 16 follows the behavior of
Qualcomm's Windows USB4 driver as determined by static analysis; no vendor
code is included.
