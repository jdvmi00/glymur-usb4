# Patch series

Apply all patches in [series](series) order on the preserved Surface 1.17
prerequisites over Linux 7.3-rc2. The [reconstruction helper](../docs/REPRODUCE.md)
does this and checks the exact final source. Numbers below identify review
boundaries, not independently validated build targets.

Patches 01-09 give the series as of Surface candidate 1.130, when the router
was still stopped and restarted around every system sleep. Patches 10-16 add
the 1.131-1.151 work: a connected router kept across s2idle and two separate
fixes. [The change list](../docs/CHANGES-1.151.md) maps each candidate to a
patch.

| Patch | Review area | Purpose / dependencies |
| --- | --- | --- |
| [01](0001-phy-qualcomm-usb4.patch) | Qualcomm hardware | PHY modes, tables and lifecycle; USB4 release and runtime PM fixes; used by 04-05, 10 and 16 |
| [02](0002-clk-qcom-usb4.patch) | Qualcomm hardware | Clock/mux operations, reset errors, USB power domain retention; used by 05, 07, 11 and 16 |
| [03](0003-thunderbolt-shared-host.patch) | Shared USB4 host | NHI transport, DMA and teardown; required by 05. Also carries the `CONFIG_USB4_QCOM`-guarded driver registration, which references symbols from 05 |
| [04](0004-usb-qcom-glink-dock.patch) | Qualcomm hardware / USB | GLINK mode handling; DWC3, xHCI and hub behavior for tunnelled links; no symbols from 01, integrates with 05 |
| [05](0005-thunderbolt-qcom-router.patch) | Qualcomm USB4 host | Router, firmware, Type-C, power and DP provider, stopped around sleep; uses 01-04 and couples to 06-07 |
| [06](0006-drm-msm-dpu-routing-dsc.patch) | Display | DPU routing/power, quad-pipe DSC, geometry, KMS ownership of the saved modeset around USB4 sleep; supplies 07 |
| [07](0007-drm-msm-dp-tunneling.patch) | Display | DP tunneling, AUX/EDID, FEC/DSC, lifecycle and sleep entry points; uses 05-06, needs the writable DP input link clock divider from 02 at runtime |
| [08](0008-arm64-dts-qcom-usb4.patch) | Shared Qualcomm descriptions | Glymur/Hamoa PHY and router descriptions; DEPOCHANGE quirk on the Glymur Type-C controllers |
| [09](0009-arm64-dts-surface-usb4.patch) | Surface board | Mahua Surface Laptop 8 routing and enablement; requires the preceding stack |
| [10](0010-phy-qcom-qmp-combo-usb4-sleep-clamp.patch) | Qualcomm hardware | USB4 clamp across system sleep; used by 16 |
| [11](0011-clk-qcom-glymur-usb4-wakeup-path.patch) | Qualcomm hardware | Router and PHY power domains kept on the wakeup path; used by 16 |
| [12](0012-thunderbolt-usb3-reactivation-delay.patch) | Shared USB4 host | USB3 re-activation delay when resume discovery tears down an enabled adapter; independent, applies to stock `tb.c` |
| [13](0013-usb-dwc3-qcom-vbus-override-in-sleep.patch) | USB | dwc3-qcom VBUS override deferred while suspended; independent of USB4 |
| [14](0014-usb-dwc3-usb4-tunnel-sleep.patch) | USB | DWC3 core kept for a tunnelling port; xHCI ordered after the router; used by 16 |
| [15](0015-drm-msm-dpu-usb4-route-cache.patch) | Display | USB4 DP route cached while the DPU is not active; used by 16 |
| [16](0016-thunderbolt-qcom-router-sleep.patch) | Qualcomm USB4 host | Connected router kept across s2idle; xHCI and PHY held while running; uses 10-12 and 14-15 at runtime |

Patches 05-07 share a host/display API and must be reviewed together; 16
extends the same files. The series preserves the tested implementation rather
than adding temporary stubs or changing behavior to make intermediate prefixes
compile. Each patch explains its purpose and retained attribution. Full-series
source reconstruction and tests pass, and the full series builds; per-prefix
compilation/bisectability remains work for upstream submission, along with
splitting mixed-purpose file changes more finely. Patches 12 and 13 fix stock
code, also apply to stock 7.3-rc2 on their own (13 with line offsets), and are
the nearest to separate upstream submissions.

For the tested configuration, `reproduce/kernel.config` includes
`CONFIG_ARCH_QCOM=y`, `CONFIG_USB4=m`, `CONFIG_USB4_QCOM=y`,
`CONFIG_PHY_QCOM_QMP_COMBO=y`, `CONFIG_QCOM_PMIC_GLINK=m`, `CONFIG_DRM_MSM=m`,
`CONFIG_DRM_MSM_DPU=y` and `CONFIG_DRM_MSM_DP=y`. These are key settings, not
a complete standalone config fragment; clock, interconnect and board dependencies
are retained in the full configuration.

Builders targeting another device should supply that board's description rather
than use patch 09. Omitting 09 alone does not establish a portable or tested
subset: shared SoC descriptions, diagnostic defaults and hardware dependencies
still need review. Original author records remain under `provenance/`; those
reference patches must not be applied a second time.
