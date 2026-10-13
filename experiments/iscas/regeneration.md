# GREENS physical regeneration (optional and expensive)

[Frozen-evidence claim reproduction](reproduction.md) is the reviewer workflow. Regeneration creates a new physical implementation and therefore a new evidence identity; its output cannot silently replace a frozen measurement.

## Requirements and frozen inputs

Use Linux/WSL, Docker with Linux/amd64 support, adequate RAM/disk, and the [manifest-pinned toolchain](../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/RUN_MANIFEST.json). OpenROAD 26Q3-1080, OpenSTA 3.1.0, and Yosys 0.68+post define the retained tool conditions. Exact external environment pins are consumed automatically from machine-readable integrity metadata.

Inputs include [ORFS configs](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/orfs/), [SDC](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/configs/common.sdc), [wrapper RTL](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/validation/rtl/matched_memory_tops.sv), and [SRAM22 macro views](../../campaigns/iscas_sustainability_extension/memory_compiler/gate3_attempt09_sram22_residual_interface_drv_and_provenance_closure/source_checkout/). Macro views are inherited SRAM22 evidence, not newly generated OpenRAM output. Preserve upstream licenses.

## One physical point using the retained interface

The following Bash procedure translates the frozen runner's actual commands to configurable local mounts. It writes only a fresh scratch run, while mounting source evidence read-only. It has been inspected against the retained runner; it was not executed as part of this documentation overhaul. Pulling/running the container and a full physical sweep are optional, substantial work.

Declare a new campaign ID, source/config hashes, tool pins, seed/clock/PVT, output location, resource limits, failure semantics, and a fixed total deadline before executing. Use an empty output directory; do not reuse an earlier run.

```bash
set -euo pipefail
PROJECT_ROOT="$(pwd)"
RUN_ROOT="$PROJECT_ROOT/tmp/physical-regeneration/secded_seed13"
test ! -e "$RUN_ROOT"
mkdir -p "$RUN_ROOT"
IMAGE="$(python -c 'import json; print(json.load(open("experiments/iscas/generated/integrity/tool_environment.json"))["container_image"])')"
CONFIG="/repo/campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/orfs/secded.mk"
flow() {
  docker run --rm --platform linux/amd64 \
    --volume "$PROJECT_ROOT:/repo:ro" --volume "$RUN_ROOT:/campaign-run" \
    --workdir /OpenROAD-flow-scripts/flow "$IMAGE" \
    make "DESIGN_CONFIG=$CONFIG" WORK_HOME=/campaign-run \
    FLOW_VARIANT=clk10p0ns_seed13 GPL_RANDOM_SEED=13 GRT_SEED=13 OR_SEED=13 \
    CLOCK_PERIOD=10.0 ABC_CLOCK_PERIOD_IN_PS=10000 "$@"
}
flow /campaign-run/results/sky130hd/secded_matched_sram_top/clk10p0ns_seed13/3_3_place_gp.odb \
  > "$RUN_ROOT/place-driver.log" 2>&1
RESULTS="$RUN_ROOT/results/sky130hd/secded_matched_sram_top/clk10p0ns_seed13"
# The campaign's common documented transition-stage bypass:
cp "$RESULTS/3_3_place_gp.odb" "$RESULTS/3_4_place_resized.odb"
flow finish > "$RUN_ROOT/finish-driver.log" 2>&1
```

This bypass is a declared flow exception, not signoff. Final DRVs, setup, hold, and output hashes must remain reported. For the corresponding Hsiao point, the retained config is `orfs/hsiao.mk` and top is `hsiao_matched_sram_top`; use a separate empty run root and identical controls. The [historical runner](../../campaigns/iscas_sustainability_extension/green_v3_2_matched_openram_orfs_validation/scripts/run_orfs_campaign.py) records the complete architecture/clock/seed matrix and collection logic. Its default behavior writes historical campaign reports, so do not invoke it in the frozen source checkout.

## Extend to activity-qualified energy

Routing alone produces no E5 energy record. A new population must generate operation-specific routed-netlist activity, preserve VCD/window/count/workload hashes, annotate required macro output roots, load the corresponding final netlist and SPEF, collect power, and qualify the same ECC-logic boundary. Inspect [execute_e5_job.py](../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/scripts/execute_e5_job.py) and [activity remediation](../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/scripts/remediate_routed_activity.py) for the actual historical protocol. Port that machinery to a new campaign contract and namespace; the original queue, outputs, and 54,000-second deadline remain sealed.

Retain noncompleted runs and timing failures. Admit matched decisions only after service, source identity, route, setup, hold, and operation gates pass. Macro-internal energy and whole-SRAM lifecycle conclusions still need separately qualified operands. [ORFS context](../../docs/physical_validation/orfs.md) · [Limitations](../../docs/limitations.md)
