# Results and limits

Scope: 13.8-inch, 12-core Mahua Surface Laptop 8 and Dell U5226KW, through
17 September 2026. These results do not establish support on other X2 boards.

**Previously tested:** clean ARM build, 3,630 module checks and a headers smoke
build; installed default boot with automatic 6144×2560/59.991 Hz and internal
2304×1536/120 Hz; physical USB4 reconnect without reboot; Dell USB/Ethernet
traffic with matching 256 MiB checksums in both directions; battery energy
rising 51.04→51.78 Wh after reconnect. The 1.17 recovery assets remain preserved.

**Still open:** HDMI-selected Dell internal-hub/Ethernet resets, independently
reproduced on an M5 Max MacBook with the same cable/monitor. The cause remains
unresolved. UCSI charging telemetry disagrees with measured recharge. PCIe
tunneling, Thunderbolt 3, other routers/ports, suspend/resume, audio persistence
and complete fresh-install/update/recovery paths remain unvalidated. External
6K120 is not working; DSPP color processing and graphics workarounds remain open.

## Source checks

The nine-patch reconstruction matches all 93 recorded source fingerprints and
the final configuration. Every file diff and hunk from the previous aggregate
is preserved exactly, apart from normalized diff path prefixes. The patch
series has no duplicated or omitted file changes. Intermediate patch prefixes
have not been independently compiled. Five extracted-C suites pass on x86_64
with Python 3.14.7/GCC 16.2.1:

| Suite | Cases passed | Negative controls rejected |
| --- | ---: | ---: |
| FEC readiness/restart | 11,364 | 5 |
| DPU route restoration | 100 | 3 |
| Plane split reset | 240 | 2 |
| USB4 idle status | 1,024 | 3 |
| IRQ/clock lifecycle | 576 | 2 |

Total: 13,304 cases and 15 negative controls; the DPU suites also pass
ASan/UBSan. These simulate selected functions, not physical links, timing or
concurrency. No new kernel build or hardware tests were run for this cleanup.

Code review was completed before this source snapshot was prepared. The
post-review corrections clarify dependencies in patches 03, 04 and 07; their
C/device-tree hunks are unchanged. Publication preparation leaves all kernel
patch inputs unchanged. The test harness now converts assertion aborts to exit
134, preserving the assertion message without invoking system crash handlers.
Negative controls must return that exact status; another nonzero status is a
test failure. This review does not establish upstream acceptance or extend
the hardware coverage above.
