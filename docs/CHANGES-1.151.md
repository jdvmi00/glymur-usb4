# Changes from 1.89 to 1.151

Every Surface kernel candidate between the 1.89 series and the tested 1.151
kernel, and what this series does with it. "In" changes are folded into the
patches named; "out" changes stay in the Surface kernel only. Superseded
experiments are in the chain but replaced before 1.151, so only their final
form appears. `provenance/derivation.json` (`update_1_151`) records the same
list with the input hashes.

Not in the 1.151 chain: 1.101 changed only the configuration, 1.108 was
withdrawn, 1.110-1.112 tested backlight changes, and 1.148 and 1.150 were USB3
delay tests that led to 1.151. 1.152 came later and is not included.

## Included

| Candidate | Change | Patch |
| --- | --- | --- |
| 1.90, 1.91, 1.96 | The router is powered only while it runs, stops and restarts around system sleep, releases its block reset before power-off, and starts runtime-active so its idle drops the CX vote | 05 |
| 1.90 | Ten Glymur USB power domains kept in retention, as on X1E | 02 |
| 1.93, 1.95, 1.103, 1.104 | Combo PHY: USB4 always-on toggle restored on exit; no DP power-on in USB3-only mode; clocks registered before runtime PM; no runtime suspend before the USB PHY is powered on | 01 |
| 1.93, 1.102, 1.105, 1.116, 1.117 | DWC3: no missing-hcd oops; xHCI no longer initializes the PHYs; PHY host mode before the xHCI starts; connection wake triggers prepared before a later host starts, firmware policy kept for the first | 04 |
| 1.118 | Display state saved and stopped before the router stops for sleep, restored after it returns | 05, 06, 07 |
| 1.119-1.122 | Cleanup: manual router, register, DP resource and tunnel controls, 26 experiment parameters, status views, diagnostic AUX reads and dock tracing removed; `tb.c`, `tb.h`, `usb4.c` back to stock; `pmic_glink_altmode` override parameter removed | 03-07 |
| 1.123, 1.127, 1.129 | September USB3 link power policy removed; U1 skipped on tunnelled links, U2 kept; `xhci.c` and `usb/quirks.h` back to stock | 04 |
| 1.130 | `snps,dis-del-phy-power-chg-quirk` on the Glymur Type-C controllers (DEPOCHANGE cleared) | 08 |
| 1.142 | USB4 clamp across system sleep | 10 |
| 1.131, 1.142 | Router and PHY power domains kept on the wakeup path | 11 |
| 1.151 | USB3 re-activation delay whenever resume discovery tears down an enabled USB3 adapter | 12 |
| 1.144 | dwc3-qcom: role-switch VBUS override deferred while suspended (unplug during sleep reset the SoC) | 13 |
| 1.139, 1.142 | DWC3 keeps a tunnelling controller across sleep (clean form of the 1.141 experiment); its xHCI resumes after the router | 14 |
| 1.137 | DPU caches the USB4 DP route while not active | 15 |
| 1.142, 1.143, 1.146, 1.147, 1.149 | Connected router kept across s2idle (router sleep, MCU halt, warm restart, link resume; clean form of the 1.131-1.141 experiments), partner that left during sleep, xHCI and PHY held while running, display wait only after a driven sink | 16 |

Superseded experiments: 1.114 and 1.115 (dock diagnostics), 1.124-1.126 and
1.128 (USB3 link power), 1.132-1.136, 1.138, 1.140, 1.141 (sleep experiments,
replaced by 1.142) and 1.145 (replaced by 1.146).

## Left out

| Candidate | Change | Reason |
| --- | --- | --- |
| 1.90 | qrtr resends HELLO on MHI resume (backport, Daniel J Blueman) | Wi-Fi |
| 1.92 | GMU driver (Akhil P Oommen RFT series), crypto node disabled | GPU and clock sync_state |
| 1.92, 1.101 | Configuration: schedutil governor, SCMI memlat options | Not USB4; `reproduce/kernel.config` is unchanged |
| 1.94, 1.95, 1.97 | Lid switch, Bluetooth power and address (including Manivannan Sadhasivam's hci_qca patch), ath12k firmware MAC, `wifi@0` | Board input and wireless |
| 1.97, 1.98 | Touchscreen and touchpad power and timing | Surface input devices |
| 1.99, 1.106 | Platform profiles without ACPI; Surface platform profile | Power profiles |
| 1.100 | Board supply rails for USB, PCIe 5 and TCSR; lid wake edges; RPMh enable state; Qualcomm SCMI memlat and ADSP SMMU IDs | Board power and memory scaling, not USB4-specific |
| 1.106 | qmp-usb pipe clock (USB-A), Sharp panel entry, eUSB2 repeater leakage fix (Krishna Kurapati) | USB-A port, internal panel, repeater power |
| 1.107, 1.109 | PCI D3cold with bridge wakeup; SSD 3.3 V supply | PCIe and storage sleep power |
| 1.113 | PWM backlight (baseline patch 0010 dropped), PMK8850 PWM, DPU core clock per layer mixer | Internal panel backlight and DPU clock power |

## Files that also carry left-out changes

Five files the series touches contain left-out changes in 1.151. The series
keeps them without those changes; applying the listed candidates' hunks gives
the 1.151 file exactly.

| File | Left-out change |
| --- | --- |
| `arch/arm64/boot/dts/qcom/glymur.dtsi` | 1.100 SCMI memlat nodes and ADSP stream IDs |
| `arch/arm64/boot/dts/qcom/glymur-microsoft-surface-laptop8.dts` | 1.92, 1.94, 1.95, 1.97, 1.98, 1.100, 1.109, 1.113 board changes |
| `drivers/gpu/drm/display/drm_dp_helper.c` | 1.113 no longer applies baseline patch 0010 |
| `drivers/gpu/drm/msm/disp/dpu1/dpu_plane.c` | 1.113 DPU core clock per layer mixer |
| `drivers/gpu/drm/msm/msm_drv.h` | 1.92 GMU driver |
