# Results and limits

Scope: 13.8-inch, 12-core Mahua Surface Laptop 8 with the Microsoft Surface
Thunderbolt 4 Dock and a Dell U5226KW, through the 1.151 kernel installed on
5 October 2026 (since 7 October the same source is installed as the
`linux-surface-laptop8` 7.3rc2.sl8.151-1 package). These results do not
establish support on other X2 boards.

The hardware results come from the Surface's own 1.151 kernel, which also
carried the changes this series leaves out ([change list](CHANGES-1.151.md)).
The tree reconstructed from this repository has been built (below) but not
booted.

## Hardware results

**1.151** (installed default since 5 October):

- Dock with a Samsung T5 and its Ethernet attached at boot: the USB4 link runs
  on two lanes at 20 Gb/s each; dock hubs, audio and Ethernet enumerate and
  the T5 on the dock runs at 10 Gb/s. On the first default boot the display
  was ready at 1.7 s and the dock found at 4.2 s.
- Two docked s2idle cycles: the router stays connected; the dock's USB3 hub
  and T5 come back within about 1.2 s of each resume. The dock loses its own
  router configuration during sleep, so its USB3 devices re-enumerate after
  each wake.
- Dock unplugged while asleep: a clean disconnect after wake; plugged back
  in, dock and T5 return in about 2.5 s. No new kernel warnings.

**Earlier candidates** in this series:

- 1.149: the dock comes up within a couple of seconds of plugging in and
  stayed up idle for 2 minutes; undocked, the PHY, controller and router
  runtime-suspend within about 5 s; a USB3 drive on the same port enumerates
  at 10 Gb/s.
- 1.147: a Dell connected through the dock returns after docked sleep;
  without a monitor on the dock the internal panel returns at once.
- 1.144: unplugging a T5, a USB 2 device or the dock while asleep no longer
  resets the Surface. It did on 1.129, 1.142 and 1.143; the faulty code is in
  stock 7.3-rc2.
- 1.129 and 1.130: 1 GB transfers to the dock Ethernet (176-187 MB/s) and
  1 GiB reads from the T5 (about 505 MB/s) with idle gaps; the tunnelled hub
  runs with U1 off, U2 on and runtime suspend allowed.
- 1.113 (28 September): Dell U5226KW over USB4 at 6144×2560/60 Hz with its
  USB3 tunnel; its hubs showed no devices until a Dell power cycle, then came
  up at 10 Gb/s and its 2.5G Ethernet got an address. Direct Dell USB4 use was
  not repeated on 1.151.
- 1.89: USB-C to HDMI cables, a USB-C HDMI hub and a USB3 drive work on first
  plug without starting the router; a Dell hot plug starts it in about 70 ms
  and unplugging stops it 0.5 s after the DisplayPort tunnel is released;
  booting with the Dell attached reaches the login prompt in about 2 s.
- 1.85: automatic 6144×2560/59.991 Hz and internal 2304×1536/120 Hz, physical
  reconnect without reboot, Dell Ethernet traffic with matching 256 MiB
  checksums in both directions, and battery energy rising 51.04→51.78 Wh
  after reconnect.

**Still open:**

- Docked boot stall: about 1 boot in 13 with the dock shows the display at
  about 35 s instead of 2 s (seen on 1.116, 1.135 and 1.141; not in 19 boots
  on 1.142-1.147). The suspected HPD/AUX race during display bind is not
  confirmed.
- Overnight docked sleep and its power draw are untested; only short docked
  sleeps passed.
- Dell recovery: the Dell's hubs needed a monitor power cycle on 1.113, and
  once on 1.99/1.104 its DP tunnel never trained until one. HDMI-selected
  Dell internal-hub/Ethernet resets also reproduced on an M5 Max MacBook.
  Exceptional disconnect/sleep recovery and endurance are unvalidated.
- Code reading: when the reconnect after hibernation or after a failed kept
  sleep fails, the router stays running without a partner until the next
  Type-C event. On a USB4-tunnelled link the device may still be allowed to
  initiate U1 itself (only hub-initiated U1 is skipped). Neither was observed
  on hardware.
- Each router start still logs "device links to tunneled native ports are
  missing" (the Thunderbolt core looks for ACPI links; the series adds its
  own device links) and an RX overflow on ring 0; neither is explained.
- The second USB-C port has no USB4 router support yet. PCIe tunneling,
  Thunderbolt 3, audio persistence and fresh-install/update/recovery paths
  are unvalidated. External 6K120 does not work; DSPP color processing and
  graphics workarounds remain open. UCSI charging telemetry disagrees with
  measured recharge.

## Source checks

The 16-patch reconstruction matches all 98 recorded source fingerprints and
the configuration. 93 of those files equal their 1.151 versions; the other
five equal 1.151 once the left-out candidate hunks are applied. Over the
whole tree, the reconstruction differs from the 1.151 build tree only in
files the left-out changes touch. Regenerating the 1.89 sections with the
same command reproduces all 93 byte for byte, and 60 are unchanged. The
patch series has no duplicated or omitted file changes within 01-09 or
within 10-16. Intermediate patch prefixes have not been compiled; the state
after patch 09 corresponds to candidate 1.130 but was not built separately.

## Build check

The reconstructed tree was built once on the DGX Spark in the existing
AArch64 builder container (GCC 16.1.1) with `reproduce/kernel.config`:
`olddefconfig` left the configuration unchanged, and `Image`, all 3,630
modules and the device trees built without errors. The build printed the same
11 warnings as the clean 1.113 Surface build, none in a file the series
touches. No package was made and nothing was installed or booted. That build
still used the tested kernel's release suffix, `-1.151-aarch64`; the helper
now writes `-1.151-glymur-usb4`, and no source file changed.

## Simulated tests

Thirteen extracted-C suites pass on x86_64 with Python 3.14.7 and GCC 16.2.1:

| Suite | Cases passed | Negative controls rejected |
| --- | ---: | ---: |
| FEC readiness/restart | 11,364 | 5 |
| DPU route restoration | 68 | 5 |
| Plane split reset | 240 | 2 |
| USB4 idle status | 1,024 | 3 |
| IRQ/clock lifecycle | 576 | 2 |
| Router port ownership and sleep | 29 | 15 |
| PHY Type-C mode, exit and sleep clamp | 17 | 10 |
| DP HPD deferral | 10 | 10 |
| MSM KMS USB4 sleep ownership | 7 | 5 |
| DP provider sleep | 12 | 5 |
| Tunnelled USB3 link power | 51 | 4 |
| dwc3-qcom VBUS override in sleep | 19 | 5 |
| USB3 resume delay | 6 | 4 |

Total: 13,423 cases and 75 negative controls; all suites build with
ASan/UBSan. The suites compile the real functions from the reconstructed
tree against simulated hardware and callbacks; they do not model physical
links, timing or concurrency. The negative controls are deliberate source
mutations, including the 1.89-era behavior where it changed, and must fail
with the assertion exit status 134.

The 1.151 update changed five suites: route restoration for the cached DPU
route (1.137), port ownership rewritten for router power, the stop-and-restart
and kept-router sleep paths (1.90-1.149), the PHY suite for the always-on
toggle and sleep clamp (1.93, 1.142), and two suites only for log messages
moved to debug output. Five suites are new. The Surface project removed most
of its older offline tests as stale; the remaining suites here still run
against 1.151 because they were updated rather than dropped. The plane split
suite runs against this series but not against the Surface 1.151 file, whose
left-out DPU clock change adds code its harness does not stub.

The test harness converts assertion aborts to exit 134, preserving the
assertion message without invoking system crash handlers. This review does
not establish upstream acceptance or extend the hardware coverage above.
