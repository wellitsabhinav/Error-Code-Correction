#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" != "0" ]]; then
  echo "Run as root inside Ubuntu WSL2." >&2
  exit 2
fi
readonly evidence_root="/var/lib/green-ecc-gate04"
readonly policy="$evidence_root/policy"
readonly snapshot="$policy/repo_snapshot"
readonly matrix="$snapshot/docs/date2027/rigour_gate_04/FLOW_RUN_MATRIX.csv"
readonly amended_runner="/var/lib/green-ecc-gate04/amendments/02/run_flow.sh"
(cd "$policy" && sha256sum --check frozen-bundle.sha256 >/dev/null)
test -f "$matrix"

failed=0
completed=0
while IFS='|' read -r run_id implementation_id config clock seed top n k kind; do
  selected_run_id="$run_id"
  base_id="${run_id%-attempt1}"
  validated="false"
  for attempt_root in "$evidence_root/runs/${base_id}"-attempt*; do
    [[ -d "$attempt_root" ]] || continue
    if [[ -f "$attempt_root/run-validation.json" ]] && grep -q '"status": "PASS"' "$attempt_root/run-validation.json"; then
      if grep -q '"exit_status": 0' "$attempt_root/run-metadata.json" 2>/dev/null || { [[ -f "$attempt_root/amendment02-validation-metadata.json" ]] && grep -q '"status": "PASS"' "$attempt_root/amendment02-validation-metadata.json"; }; then
        validated="true"
        echo "GATE04_MATRIX_EXISTING run=$(basename "$attempt_root") action=validated-no-retry"
        break
      fi
    fi
  done
  if [[ "$validated" == "true" ]]; then
    continue
  fi
  attempt=1
  while [[ -e "$evidence_root/runs/${base_id}-attempt${attempt}" ]]; do
    attempt=$((attempt + 1))
  done
  selected_run_id="${base_id}-attempt${attempt}"
  if [[ "$selected_run_id" != "$run_id" ]]; then
    echo "GATE04_MATRIX_VISIBLE_RETRY original=$run_id retry=$selected_run_id"
  fi
  set +e
  bash "$amended_runner" "$selected_run_id" "$implementation_id" "$config" "$clock" "$seed" "$top" "$n" "$k" "$kind"
  status=$?
  set -e
  completed=$((completed + 1))
  if [[ $status != 0 ]]; then
    failed=$((failed + 1))
  fi
done < <(python3 -c 'import csv,sys; rows=csv.DictReader(open(sys.argv[1],encoding="utf-8",newline="")); [print("|".join(row[key] for key in ("run_id","implementation_id","config","clock_period_ns","physical_seed","design_top","n","k","kind"))) for row in rows]' "$matrix")

echo "GATE04_MATRIX_DONE attempted=$completed failed=$failed"
test "$failed" -eq 0
