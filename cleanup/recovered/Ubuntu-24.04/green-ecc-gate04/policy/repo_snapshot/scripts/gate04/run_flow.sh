#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "Run as root inside Ubuntu WSL2." >&2
  exit 2
fi
if [[ $# != 9 ]]; then
  echo "usage: run_flow.sh RUN_ID IMPLEMENTATION_ID CONFIG CLOCK_NS SEED TOP N K KIND" >&2
  exit 3
fi

readonly run_id="$1"
readonly implementation_id="$2"
readonly config="$3"
readonly clock_ns="$4"
readonly seed="$5"
readonly top="$6"
readonly n="$7"
readonly k="$8"
readonly kind="$9"
readonly image="openroad/orfs@sha256:f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e"
readonly evidence_root="/var/lib/green-ecc-gate04"
readonly policy="$evidence_root/policy"
readonly snapshot="$policy/repo_snapshot"
readonly host_root="$evidence_root/runs/$run_id"
readonly container_root="/gate04-run"
readonly config_path="/gate04-repo/scripts/gate04/configs/$config"
readonly cid_file="/tmp/green-ecc-gate04-${run_id}.cid"

(cd "$policy" && sha256sum --check frozen-bundle.sha256 >/dev/null)
test -f "$snapshot/scripts/gate04/configs/$config"
test ! -e "$host_root"
test ! -e "$cid_file"
mkdir "$host_root"

printf '%s\n' \
  "RUN_ID=$run_id" \
  "IMPLEMENTATION_ID=$implementation_id" \
  "CLOCK_PERIOD=$clock_ns" \
  "GPL_RANDOM_SEED=$seed" \
  "GRT_SEED=$seed" \
  "OR_SEED=$seed" \
  "DESIGN_NAME=$top" \
  "CODEWORD_BITS=$n" \
  "USEFUL_BITS=$k" \
  "KIND=$kind" \
  > "$host_root/effective-run-environment.log"
printf '%s\n' \
  "docker image: $image" \
  "make DESIGN_CONFIG=$config_path" \
  > "$host_root/run-command.txt"

readonly start_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
docker run --rm --platform linux/amd64 \
  --cidfile "$cid_file" \
  --volume "$host_root:$container_root" \
  --volume "$snapshot:/gate04-repo:ro" \
  --entrypoint /bin/bash \
  "$image" \
  -lc "set -euo pipefail; source /OpenROAD-flow-scripts/env.sh; export LEC_CHECK=0 NUM_CORES=1 WORK_HOME=$container_root CLOCK_PERIOD=$clock_ns GPL_RANDOM_SEED=$seed GRT_SEED=$seed OR_SEED=$seed; cd /OpenROAD-flow-scripts/flow; make DESIGN_CONFIG=$config_path" \
  > "$host_root/container.log" 2>&1
status=$?
set -e

container_id="UNAVAILABLE"
if [[ -s "$cid_file" ]]; then
  container_id="$(tr -d '\r\n' < "$cid_file")"
  rm -f "$cid_file"
fi

readonly results="$host_root/results/sky130hd/$top/base"
readonly logs="$host_root/logs/sky130hd/$top/base"
readonly reports="$host_root/reports/sky130hd/$top/base"
failure_reason=""
if [[ $status == 0 ]]; then
  for artifact in \
    1_synth.odb 2_floorplan.odb 3_place.odb 4_cts.odb 5_route.odb \
    6_final.odb 6_final.v 6_final.sdc 6_final.def 6_final.gds 6_final.spef; do
    if [[ ! -s "$results/$artifact" ]]; then
      status=91
      failure_reason="missing required artifact $artifact"
      break
    fi
  done
fi
if [[ $status == 0 && ! -s "$logs/6_report.json" ]]; then
  status=92
  failure_reason="missing machine-readable post-route report"
fi
if [[ $status == 0 ]]; then
  if grep -Eq '\$_|\\\$[a-zA-Z_]' "$results/6_final.v"; then
    status=93
    failure_reason="generic or internal cell escaped into final netlist"
  fi
fi
if [[ $status == 0 ]]; then
  if grep -E '^module[[:space:]]+' "$results/6_final.v" | grep -vq "$top"; then
    status=94
    failure_reason="unexpected module retained in final netlist"
  fi
fi

if [[ $status == 0 ]]; then
  case "$implementation_id" in
    secded-rtl-combinational-72-64-v1)
      gold_files="scripts/gate03r/rtl/secded_characterization_tops.sv,scripts/gate04/rtl/gate04_boundaries.sv"
      ;;
    secded-rtl-pipelined-72-64-v1)
      gold_files="asic/rtl/secded/secded_pipelined_72_64_v1.sv,scripts/gate04/rtl/gate04_boundaries.sv"
      ;;
    hsiao-generated-combinational-72-64-v1)
      gold_files="green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_encoder.sv,green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_syndrome.sv,green_ecc_physical_simulation/rtl/hsiao_secded_72_64/hsiao_secded_72_64_v1_decoder.sv,scripts/gate04/rtl/gate04_boundaries.sv"
      ;;
    shortened-bch-78-64-t2-v1-rtl-syndrome-chien-v1)
      gold_files="asic/rtl/bch/bch_78_64_t2_v1.sv,scripts/gate04/rtl/gate04_boundaries.sv"
      ;;
    boundary-reference-72-64-v1|boundary-reference-78-64-v1)
      gold_files="scripts/gate04/rtl/gate04_boundaries.sv"
      ;;
    *)
      status=95
      failure_reason="unknown equivalence source set"
      gold_files=""
      ;;
  esac
fi
if [[ $status == 0 ]]; then
  set +e
  bash "$snapshot/scripts/gate04/mapped_equivalence.sh" \
    "$host_root" "$snapshot" "$top" "$gold_files" mapped "$host_root/mapped-equivalence.log"
  mapped_status=$?
  bash "$snapshot/scripts/gate04/mapped_equivalence.sh" \
    "$host_root" "$snapshot" "$top" "$gold_files" postroute "$host_root/postroute-equivalence.log"
  postroute_status=$?
  set -e
  if [[ $mapped_status != 0 || $postroute_status != 0 ]]; then
    status=98
    failure_reason="exact RTL-to-mapped or RTL-to-postroute equivalence failed"
  fi
fi

if [[ $status == 0 ]]; then
  clock_label="${clock_ns%.*}ns"
  case "$implementation_id" in
    secded-rtl-combinational-72-64-v1|secded-rtl-pipelined-72-64-v1)
      families="conventional_secded"
      ;;
    hsiao-generated-combinational-72-64-v1)
      families="hsiao"
      ;;
    shortened-bch-78-64-t2-v1-rtl-syndrome-chien-v1|boundary-reference-78-64-v1)
      families="bch78"
      ;;
    boundary-reference-72-64-v1)
      families="conventional_secded hsiao"
      ;;
    *)
      status=95
      failure_reason="unknown trace family"
      families=""
      ;;
  esac
fi

if [[ $status == 0 ]]; then
  trace_specs=""
  for family in $families; do
    for trace_class in no_error single_error double_error; do
      label="${family}-${trace_class}"
      path="/gate04-policy/traces/${family}-${clock_label}-${trace_class}.vcd.gz"
      if [[ -n "$trace_specs" ]]; then trace_specs+=","; fi
      trace_specs+="${label}|${path}"
    done
  done
  mkdir "$host_root/power"
  set +e
  docker run --rm --platform linux/amd64 \
    --volume "$host_root:$container_root" \
    --volume "$snapshot:/gate04-repo:ro" \
    --volume "$policy:/gate04-policy:ro" \
    --entrypoint /bin/bash \
    "$image" \
    -lc "set -euo pipefail; source /OpenROAD-flow-scripts/env.sh; export LEC_CHECK=0 NUM_CORES=1 WORK_HOME=$container_root CLOCK_PERIOD=$clock_ns GPL_RANDOM_SEED=$seed GRT_SEED=$seed OR_SEED=$seed GATE04_POWER_DIR=$container_root/power GATE04_TRACE_SPECS='$trace_specs'; cd /OpenROAD-flow-scripts/flow; make DESIGN_CONFIG=$config_path RUN_SCRIPT=/gate04-repo/scripts/gate04/gate04_power.tcl RUN_LOG_NAME_STEM=gate04_power run" \
    > "$host_root/power-container.log" 2>&1
  power_status=$?
  set -e
  if [[ $power_status != 0 ]]; then
    status=96
    failure_reason="post-route activity-based power failed with status $power_status"
  elif ! grep -q 'GATE04_POWER_PASS' "$host_root/power-container.log"; then
    status=97
    failure_reason="post-route activity-based power completion marker missing"
  fi
fi

if [[ $status == 0 ]]; then
  set +e
  python3 "$snapshot/scripts/gate04/validate_run.py" \
    --run-root "$host_root" \
    --implementation-id "$implementation_id" \
    --top "$top" \
    --n "$n" \
    --clock-ns "$clock_ns" \
    > "$host_root/run-validation.log" 2>&1
  validation_status=$?
  set -e
  if [[ $validation_status != 0 ]]; then
    status=99
    failure_reason="full physical, equivalence, or activity validation failed"
  fi
fi

readonly end_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 -c 'import json,pathlib; pathlib.Path("'"$host_root"'/run-metadata.json").write_text(json.dumps({"schema_version":1,"run_id":"'"$run_id"'","implementation_id":"'"$implementation_id"'","kind":"'"$kind"'","design_top":"'"$top"'","n":'"$n"',"k":'"$k"',"clock_period_ns":'"$clock_ns"',"physical_seed":'"$seed"',"gpl_random_seed":'"$seed"',"grt_seed":'"$seed"',"or_seed":'"$seed"',"start_time_utc":"'"$start_utc"'","end_time_utc":"'"$end_utc"'","exit_status":'"$status"',"container_id":"'"$container_id"'","failure_reason":"'"$failure_reason"'"},indent=2,sort_keys=True)+"\n",encoding="utf-8")'
(
  cd "$host_root"
  find . -type f ! -name raw-artifacts.sha256 -print0 | sort -z | xargs -0 sha256sum > raw-artifacts.sha256
)

if [[ $status != 0 ]]; then
  echo "GATE04_FLOW_FAIL run=$run_id status=$status reason=$failure_reason" >&2
  exit "$status"
fi
echo "GATE04_FLOW_PASS run=$run_id"
