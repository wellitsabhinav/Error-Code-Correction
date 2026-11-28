# Phase II: delay-aware qualification and independent baseline analysis

Status: **P2-G00 BLOCKED**. Synthetic IOPATH probes pass under the explicitly assembled two-cell models and consistent nanosecond units. The installed simulator does not provide qualified INTERCONNECT or timing-check behavior. The original DATE physical archives are missing locally. P2-G01/G02/G03 production experiments were therefore not launched.

Start with [the consolidated report](PHASE_II_RESEARCH_REPORT.md), [readiness](reports/P2_G00_READINESS.md), and [storage audit](reports/STORAGE_AUDIT.md). All existing baseline files remain unchanged. Historical estimates, synthetic measurements, software-reference observations, and unavailable results are separate.

Run from the repository root in PowerShell:

```powershell
python research/phase2/scripts/validate_phase2.py
python -m pytest -q research/phase2/tests
python research/phase2/scripts/audit_repository.py
python research/phase2/scripts/analyze_baseline.py
python research/phase2/scripts/workloads.py --count 1000 --seed 17 --vectors
python research/phase2/scripts/make_figures.py
python research/phase2/scripts/storage_manager.py audit --label reproduced
```

The cached Linux simulator is reused without installation. Exact executed qualification command:

```powershell
wsl -d AutonomousEDA -- bash -lc 'cd /mnt/c/Users/Abhinav/OneDrive/Desktop/ECC/Error-Code-Correction && python3 research/phase2/scripts/qualify_simulator.py --run-id qualification_final --consistent-timescale --iverilog /mnt/f/AgenticAI/.local/m9-icarus-linux/extracted/usr/bin/iverilog --vvp /mnt/f/AgenticAI/.local/m9-icarus-linux/extracted/usr/bin/vvp --ivl-base /mnt/f/AgenticAI/.local/m9-icarus-linux/extracted/usr/lib/x86_64-linux-gnu/ivl'
wsl -d AutonomousEDA -- bash -lc 'cd /mnt/c/Users/Abhinav/OneDrive/Desktop/ECC/Error-Code-Correction && python3 research/phase2/scripts/run_rtl_smoke.py --iverilog /mnt/f/AgenticAI/.local/m9-icarus-linux/extracted/usr/bin/iverilog --vvp /mnt/f/AgenticAI/.local/m9-icarus-linux/extracted/usr/bin/vvp --ivl-base /mnt/f/AgenticAI/.local/m9-icarus-linux/extracted/usr/lib/x86_64-linux-gnu/ivl'
```

For a fresh replay use a new run ID, such as `qualification_replay_01`, to preserve the retained run. Existing IDs preserve their original four-hour deadline and reject changed input/tool contracts; expired runs are not silently renewed. Completed historical evidence can be validated without rerunning simulation. The final run's applied SDF files and assembled model hashes are in its manifest and model-assembly record; the deterministic assembly is in the qualification script. `qualification` retains the failed cross-unit test, `qualification_ns` the earlier successful development test, and `simulator-qualification` the native compiler failures.

To reproduce the negative cross-unit experiment, omit `--consistent-timescale` and use a fresh run ID. An IOPATH-only pass never authorizes production delay-aware ECC experiments.

Streaming interface (no full-file read):

```powershell
Get-Content research/phase2/raw/qualification_final/iopath_typ.vcd | python research/phase2/scripts/activity_stream.py --input - --start-ps 5000 --end-ps 49000 --output research/phase2/scratch/reparsed.json
python research/phase2/scripts/compress_evidence.py
```

For production on Linux, feed a simulator event pipe/FIFO to the same parser after a qualified simulator exists. This entry point does not claim that compact toggle statistics can replace OpenSTA's required VCD. Power-compatible import, activity preservation, and full-net coverage remain unqualified. Do not delete a power-import waveform until those checks pass.

Safe cleanup requires an explicit completed-run manifest:

```powershell
python research/phase2/scripts/storage_manager.py cleanup --manifest research/phase2/experiments/RUN/manifest.json --dry-run
python research/phase2/scripts/storage_manager.py cleanup --manifest research/phase2/experiments/RUN/manifest.json --verified-temporary-only
```

The utility accepts only explicitly classified files below `research/phase2/scratch`, verifies retained evidence and file hashes, rejects incomplete runs and outside paths, previews removals, and logs every deletion. No real run was cleaned with this utility; destructive behavior was tested only on files created by its unit tests. Compression separately removed only byte-verified generated JSON duplicates, preserving lossless compressed evidence and every small qualification VCD.

`python research/phase2/scripts/run_checks.py --timeout 120` records the required broader checks. The sparse checkout omits unrelated validation datasets; failures from those omissions are disclosed in the consolidated report. `--seal` on the validator writes a new Phase II package manifest only after intentional report/data regeneration; it never reseals a frozen baseline campaign.
