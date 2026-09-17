# Patch series

Apply all patches in [series](series) order on the preserved Surface 1.17
prerequisites over Linux 7.3-rc2. The [reconstruction helper](../docs/REPRODUCE.md)
does this and checks the exact final source. Numbers below identify review
boundaries, not independently validated build targets.

| Patch | Review area | Purpose / dependencies |
| --- | --- | --- |
| [01](0001-phy-qualcomm-usb4.patch) | Qualcomm hardware | PHY modes, tables and lifecycle; used by 04–05 |
| [02](0002-clk-qcom-usb4.patch) | Qualcomm hardware | Clock/mux operations and reset errors; used by 05 and 07 |
| [03](0003-thunderbolt-shared-host.patch) | Shared USB4 host | NHI transport, DMA and teardown; required by 05. Also carries the `CONFIG_USB4_QCOM`-guarded driver registration and DP retry hook in shared files, which reference symbols from 05 |
| [04](0004-usb-qcom-glink-dock.patch) | Qualcomm hardware / USB | GLINK mode handling and USB host/hub behavior; no symbols from 01, integrates with 05 |
| [05](0005-thunderbolt-qcom-router.patch) | Qualcomm USB4 host | Router, firmware, Type-C and DP provider; uses 01–04 and couples to 06–07 |
| [06](0006-drm-msm-dpu-routing-dsc.patch) | Display | DPU routing/power, quad-pipe DSC and geometry; supplies 07 |
| [07](0007-drm-msm-dp-tunneling.patch) | Display | DP tunneling, AUX/EDID, FEC/DSC and lifecycle; uses 05–06, needs the writable DP input link clock divider from 02 at runtime |
| [08](0008-arm64-dts-qcom-usb4.patch) | Shared Qualcomm descriptions | Glymur/Hamoa PHY and router descriptions for the driver interfaces |
| [09](0009-arm64-dts-surface-usb4.patch) | Surface board | Mahua Surface Laptop 8 routing and enablement; requires the preceding stack |

Patches 05–07 share a host/display API and must be reviewed together. The series
preserves the tested implementation rather than adding temporary stubs or
changing behavior to make intermediate prefixes compile. Each patch explains
its purpose and retained attribution. Full-series source reconstruction and
tests pass; per-prefix compilation/bisectability remains work for upstream
submission, along with splitting mixed-purpose file changes more finely.

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
