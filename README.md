# Glymur USB4 and 6K60

Experimental Linux USB4 host, PHY and DisplayPort integration for Qualcomm
Glymur, tested on the **13.8-inch, 12-core Mahua Surface Laptop 8** with a
Microsoft Surface Thunderbolt 4 Dock and a Dell U5226KW. The series follows
Surface kernel candidate 1.151, Linux 7.3-rc2, installed on the tested
laptop since 5 October 2026. It is not upstream and not posted.

Start with **[the ordered patch series](patches/README.md)**. Sixteen patches
separate the shared host, Qualcomm hardware, display, USB and Surface changes.
They apply on top of the preserved Surface 1.17 kernel prerequisites, not
vanilla Linux. Patches 01-09 give the series as of candidate 1.130; 10-16 add
keeping a connected router across sleep and two separate fixes. The complete
series is verified and builds; individual intermediate builds and upstream
submission cleanup remain pending.

| Path | Purpose |
| --- | --- |
| `patches/` | Component patches, dependencies and application order |
| `tests/` | Thirteen extracted-C test suites |
| `reproduce/` | Baseline prerequisites, configuration and source hashes |
| `provenance/` | Original author headers and patch derivation record |

[Reconstruct and test](docs/REPRODUCE.md) · [Results and limits](docs/VALIDATION.md)
· [Changes since 1.89](docs/CHANGES-1.151.md) · [Contributing](CONTRIBUTING.md)
· [Authorship](docs/PROVENANCE.md) · [License](LICENSE.md)

What works on the tested laptop: the Surface Thunderbolt 4 Dock links on two
lanes at 20 Gb/s each with its hubs, audio and Ethernet, and stays connected
across s2idle (its USB3 devices return within about 1.2 s of wake).
Unplugging a USB device or the dock during sleep no longer resets the laptop.
The Dell U5226KW ran at 6144×2560/60 Hz over USB4 with its hub and Ethernet
on candidate 1.113; that was not repeated directly on 1.151. USB-C to HDMI
cables and hubs and USB3 drives use the port natively; the router runs only
for USB4 or Thunderbolt partners.

Still open: an occasional 35 s display delay when booting docked, overnight
docked sleep, and recovery cases with the Dell (its hubs sometimes need a
monitor power cycle). Other boards, the second USB-C port, PCIe tunneling and
external 6K120 are not working or not validated.

The Surface kernel also carries board, wireless, GPU and power changes that
are outside this series' scope, so the reconstructed source is not a byte copy
of the tested kernel: 93 of the 98 files the series touches match 1.151, and
the other five differ only by those changes. This is a source patch set, not
a supported installation release. Firmware and distribution packaging are
not included. Other boards need their own device descriptions and
validation; the Surface device tree must not be reused as-is.
