# Results and limits

Scope: 13.8-inch, 12-core Mahua Surface Laptop 8 and Dell U5226KW, through
the installed 1.89 kernel (September 2026). These results do not establish
support on other X2 boards.

**Previously tested:** clean ARM build, 3,630 module checks and a headers smoke
build; installed default boot with automatic 6144×2560/59.991 Hz and internal
2304×1536/120 Hz; physical USB4 reconnect without reboot; Dell USB/Ethernet
traffic with matching 256 MiB checksums in both directions; battery energy
rising 51.04→51.78 Wh after reconnect.

**1.89** (tested from a separate boot entry, then installed as the default
kernel with identical modules): the USB4 router no longer claims the
port at boot. USB-C to HDMI cables, a USB-C HDMI hub (3840×2160, hub USB3 at
5 Gb/s) and a USB3 drive (10 Gb/s) work on first plug without starting the
router or freezing the desktop. A Dell hot plug starts the router in about
70 ms (6K60, 2×20 Gb/s, hubs at 10 Gb/s, Ethernet); unplugging stops it 0.5 s
after the DisplayPort tunnel is released. Booting with the Dell attached shows
the login prompt within about 2 s on both screens; before the display fix it
took about 30 s, because a DisplayPort connection that had already gone away
held up USB-C event handling. No units failed.

**Still open:** HDMI-selected Dell internal-hub/Ethernet resets, independently
reproduced on an M5 Max MacBook with the same cable/monitor. The cause remains
unresolved and was not retested on 1.89. UCSI charging telemetry disagrees
with measured recharge. Suspend/resume is broken on this board: the router,
Wi-Fi and front-port USB fail after resume. PCIe tunneling, Thunderbolt 3,
other routers/ports, audio persistence and complete fresh-install/update/
recovery paths remain unvalidated. External 6K120 is not working; DSPP color processing and graphics workarounds remain open.

## Source checks

The nine-patch reconstruction matches all 93 recorded source fingerprints and
the final configuration. Every file diff and hunk from the previous aggregate
is preserved exactly, apart from normalized diff path prefixes and the seven
file diffs regenerated for 1.89. The patch series has no duplicated or
omitted file changes. Intermediate patch prefixes
have not been independently compiled. Eight extracted-C suites pass on x86_64
with Python 3.14.7/GCC 16.2.1:

| Suite | Cases passed | Negative controls rejected |
| --- | ---: | ---: |
| FEC readiness/restart | 11,364 | 5 |
| DPU route restoration | 100 | 3 |
| Plane split reset | 240 | 2 |
| USB4 idle status | 1,024 | 3 |
| IRQ/clock lifecycle | 576 | 2 |
| Router port ownership | 13 | 7 |
| PHY Type-C mode after USB4 | 13 | 6 |
| DP HPD deferral | 10 | 10 |

Total: 13,340 cases and 38 negative controls; all suites build with
ASan/UBSan. The three 1.89 suites replay recorded Type-C sequences and fail
on the 1.85 source. These simulate selected functions, not physical links, timing or
concurrency. The 1.89 kernel built from the same source hashes is the one installed
and tested above.

Code review was completed before this source snapshot was prepared. The
post-review corrections clarify dependencies in patches 03, 04 and 07; their
C/device-tree hunks are unchanged. Publication preparation leaves all kernel
patch inputs unchanged. The test harness now converts assertion aborts to exit
134, preserving the assertion message without invoking system crash handlers.
Negative controls must return that exact status; another nonzero status is a
test failure. This review does not establish upstream acceptance or extend
the hardware coverage above.
