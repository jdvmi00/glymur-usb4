# Glymur USB4 and 6K60

Experimental Linux USB4 host, PHY and DisplayPort integration for Qualcomm
Glymur, tested on the **13.8-inch, 12-core Mahua Surface Laptop 8** with a Dell
U5226KW. The tested kernel is Linux 7.3-rc2 with the patches and configuration
included here.

Start with **[the ordered patch series](patches/README.md)**. Nine patches
separate the shared host, Qualcomm hardware, display and Surface changes while
producing the same 1.89 source. They apply on top of the preserved Surface 1.17
kernel prerequisites, not vanilla Linux. The complete series is verified;
individual intermediate builds and upstream submission cleanup remain pending.

| Path | Purpose |
| --- | --- |
| `patches/` | Component patches, dependencies and application order |
| `tests/` | Eight extracted-C test suites |
| `reproduce/` | Baseline prerequisites, final configuration and source hashes |
| `provenance/` | Original author headers and patch derivation record |

[Reconstruct and test](docs/REPRODUCE.md) · [Results and limits](docs/VALIDATION.md)
· [Contributing](CONTRIBUTING.md) · [Authorship](docs/PROVENANCE.md)
· [License](LICENSE.md)

Automatic 6K60, internal 120 Hz, physical reconnect, Dell Ethernet traffic and
actual battery recharge passed bounded tests. The same port also works on
first plug with USB-C to HDMI cables and hubs and USB3 drives; the router runs
only while a USB4 or Thunderbolt partner is attached. HDMI-selected Dell hub resets
remain unresolved and also reproduced on a Mac. Other boards, PCIe tunneling,
suspend/resume and external 6K120 are not validated as working.

This is a source patch set, not a supported installation release. Firmware and
distribution packaging are not included. Other boards need their own device
descriptions and validation; the Surface device tree must not be reused as-is.
