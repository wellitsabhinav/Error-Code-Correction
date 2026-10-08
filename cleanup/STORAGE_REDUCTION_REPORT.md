# GREENS storage reduction

`GREENS_CLEANUP_PARTIAL`

| Category | Before | After | Change |
|---|---:|---:|---:|
| Ubuntu-24.04 GREENS content, excluding Git metadata | 29.330 GB | 7.336 GB | 21.993 GB removed |
| Attempt04-Recovery GREENS content, excluding Git metadata | 13.231 GB | 7.195 GB | 6.036 GB removed |
| Compressed archives on D | 0 | 3.820 GB | 16 verified archives |
| Recovery duplicate runs | 5.948 GB | 0 | 8 trees removed |

The archive originals contained 22,081,140,483 bytes over 15,007 regular files and compressed to 3,819,867,327 bytes (82.70% smaller). Eight byte-identical recovery run trees removed another 5,948,489,791 bytes. Total source file data removed: **28,029,630,274 bytes (28.030 GB)**. Net logical reduction after archives and their external member manifests: **24,205,164,320 bytes (24.205 GB)**. Public audit/documentation additions and restoration of 114 missing public files are separate small increases, not claimed as savings.

The two WSL content rescans reconcile with the executed per-file quarantine manifest. Tools, PDKs, source checkouts and uncertain files were retained. Frozen canonical duplicate paths represent 5,533,945,433 logical bytes but were not removed because manifests and scripts consume those paths/hashes; Git already shares their identical blobs.

Host F free space need not increase when ext4 blocks are freed inside an allocated VHDX. No WSL shutdown, VHDX compaction or removal was performed because the envelopes include unrelated resources and live system state. Archives use D space. Concurrent unrelated storage work changed drive free space, so observed whole-drive deltas are not attributed to this cleanup. The machine-readable inventory records final free-space observations separately.

C: retains the canonical repository, managed historical worktrees and cloud source snapshots. D: stores `GREENS_ARCHIVES` plus quarantine receipts. E: received no GREENS mutations. F: retains registered WSL envelopes, their now-smaller guest contents, the unregistered backup and active swap. G: was inspected as an extra discovery scope and received no cleanup mutations.
