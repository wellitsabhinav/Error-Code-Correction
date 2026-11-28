# Storage and infrastructure audit

Audit date: 2026-11-28. No existing user data, PDK, cache, container image, partition or virtual disk was deleted, relocated or compacted.

| Initial host measurement | Free bytes | Free GiB | Planning mode |
|---|---:|---:|---|
| C: | 27,974,656,000 | 26.05 | C: moderate constraint |
| G: | 83,306,139,648 | 77.58 | D: greater than 50 GiB |
| F: | 162,513,530,880 | 151.35 | Existing WSL host volume; not a new research installation |

`Get-PSDrive` and .NET drive information were initially available. `Get-Volume` and WSL access were denied inside the sandbox; a read-only elevated audit succeeded, with raw results retained in `raw/environment/windows_inventory.json` and `wsl_list.txt`. These are access/environment observations, not automatic-approval rejections.

The active checkout remains on C: so the workspace and reviewed source do not diverge across copies. G: is the configured preferred future scratch location but was not used to create a redundant checkout. Each bounded job checks a 3 GiB reserve plus its projected output; experiments are sequential. The Phase II output estimate is 128 MiB, with waveform limits 256 MiB/file and a 512 MiB maximum configured buffer. Production peak requirements remain unknown and would need measurement before admission.

## Existing environments

Four WSL2 registrations exist: Ubuntu-24.04, AutonomousEDA, Attempt04-Recovery and PACT-OpenSTA-Review420. Ubuntu's registered ext4 path and its configured swap-file parent are missing. No registration was removed or recreated. AutonomousEDA starts despite the swap-path warning and was reused only for public tools and this project's files.

The existing AutonomousEDA VHDX was 15,739,125,760 bytes at first discovery and 15,772,680,192 bytes at the saved audit. The latter includes guest/Docker activity, not a measured new tool installation. Guest `df` reports about 943 GiB available in its dynamically growing virtual filesystem, but the host F: free space is the real growth constraint. Host and guest capacities must not be added together. Guest inode availability is about 66.9 million; drvfs's synthetic inode counts are not treated as physical NTFS exhaustion evidence.

Guest directories: `/opt` 1.3 GiB, `/usr/local` 100 KiB, `/root/.cache` 166 MiB, and apt cache 194 MiB. One existing ORFS image occupies about 6.446 GB; there are no Docker volumes, retained containers or build cache in the audited inventory. Docker storage and VHDX lengths overlap and are not independent totals. No `prune` or cache cleanup was run.

The existing ORFS image digest is `8eff077230b86729f6248b34eeab370e486fa4052d34c60d9067e3e4aa720987`, different from the frozen baseline image `f05cee3219a02f26289f02f00e11a3fc986ab51a482a0000a2da810cda219a6e`. Its TT SKY130HD Liberty hash nevertheless matches the baseline exactly. The image reports Yosys 0.68+post with unknown Git SHA and OpenROAD version `unknown`; image identity is retained rather than inventing tool versions. Its simulator/model environment does not satisfy P2-G00.

Native Git is 2.53.0.windows.1, Python 3.12.5, Yosys 0.30+48, and Icarus is a 12.0 development build. A separate already cached Ubuntu Icarus 12.0 stable package (2,125,764-byte .deb, previously extracted) supplied the successful synthetic/RTL runs. Existing native prefixes and the Linux package were reused; no new package, Docker image or full PDK was installed. Only 22,492 bytes of public two-cell model/license source were acquired for qualification.

## Repository/artifact availability and acquisition cost

The original checkout and the archival `D:/GREENS_ARCHIVES` directory are absent. The DATE Revision-2 and breadth archives are referenced by original member/aggregate hashes; none was downloaded or regenerated. Different ISCAS physical artifacts were not substituted.

A partial Git clone with `--filter=blob:none --no-checkout` retained history needed to identify the baseline and historical bibliography. Sparse checkout excludes archives, unrelated campaigns, large raw evidence and most unrelated reports. Git's first sparse materialization attempts produced temporary packs; sampled temporary-pack bytes reached 2,061,058,023 (1.92 GiB). Later samples show about 280.16 MiB in indexed packs and 1.33 GiB in unindexed temporary packs. Those are acquisition overhead, not EDA dependencies or experimental evidence. No claim of a continuously measured exact acquisition peak is made. No manual Git-object deletion was performed.

The 128 MiB estimate applies to bounded Phase II jobs and retained results, not the initially unknown Git materialization overhead. Even the largest sampled acquisition overhead left C: well above the 3 GiB safety reserve. A future acquisition must include a larger explicit temporary-pack allowance, or retrieve exact files/objects before materializing broad directories.

The broad repository checks fail on intentionally absent sparse-checkout data, including calibration provenance, generated documentation inputs and ISCAS modules. That limits global regression validation; it is not reclassified as a Phase II scientific measurement failure. Phase II tests, RTL smoke and native build results are separately reported.

Sampled final host capacity, Phase II byte totals and compression savings are recorded in `processed/storage_history.csv`, `processed/storage_summary.json` and `STORAGE_OPTIMIZATION.md`. Free-space changes also include unrelated host activity and must not be reported as storage saved by this work.
