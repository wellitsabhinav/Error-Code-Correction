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
readonly runner="$snapshot/scripts/gate04/run_flow.sh"
readonly amended_runner="/var/lib/green-ecc-gate04/amendments/01/run_flow.sh"
(cd "$policy" && sha256sum --check frozen-bundle.sha256 >/dev/null)
test -f "$matrix"

failed=0
completed=0
while IFS='|' read -r run_id implementation_id config clock seed top n k kind; do
  selected_run_id="$run_id"
  if [[ -e "$evidence_root/runs/$run_id" ]]; then
    if [[ -f "$evidence_root/runs/$run_id/run-validation.json" ]] && grep -q '"status": "PASS"' "$evidence_root/runs/$run_id/run-validation.json"; then
      echo "GATE04_MATRIX_EXISTING run=$run_id action=validated-no-retry"
      continue
    fi
    selected_run_id="${run_id%-attempt1}-attempt2"
    test ! -e "$evidence_root/runs/$selected_run_id"
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
