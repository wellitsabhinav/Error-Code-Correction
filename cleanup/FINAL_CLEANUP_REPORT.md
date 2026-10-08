# Final GREENS cleanup report

## Executive status

**GREENS_CLEANUP_PARTIAL.** Available unique campaign material was preserved upstream, the documentation was overhauled, and verified historical archives/duplicates reclaimed 24.205 GB of net logical storage. Cloud source copies, uncertain offline material and frozen path-bound duplicates remain protected.

## Canonical repository

`C:\Users\Abhinav\OneDrive\Desktop\ECC\Error-Code-Correction`. Baseline public main: `68fd3e7020966cf74041dec0780d7e8b285ce31a`. Runtime source, CLI formats, JSON/CSV schemas, advisory ML behavior and frozen result paths retain their existing contracts.

## GitHub state

[Cleanup PR #220](https://github.com/wellitsabhinav/Error-Code-Correction/pull/220), branch `maintenance/greens-cleanup-docs-sync`. Source preservation commit `5c23c208e529df7692154071d22b2bc65354a7b9` was pushed and matched the remote head before archival. The final branch/merge commit and CI state are available in the PR metadata; no force-push or history rewrite occurred. Nine historical annotated-tag objects could not be recovered from the public remote and remain recorded in [UNRECOVERED_GIT_REFERENCES.json](UNRECOVERED_GIT_REFERENCES.json).

## Local files added to GitHub

719 unique historical files, 4,934,175 raw bytes: Ubuntu-24.04 (307), Attempt04-Recovery (16), and managed Windows checkouts (396). The Windows preservation includes 378 model scenario configurations/manifests, 17 source/test/documentation versions, and a pre-existing MUX-cost patch; its 32 focused historical tests passed. Files include reusable gate orchestration/analysis, seed helpers, OpenRAM failure/LVS helpers and compact run/provenance records. Each imported blob's SHA256 matched its reviewed original. WSL preservation was verified remotely before removal; Windows originals remain intact. 57,726 per-file audit rows record source/public-history comparisons and conservative retained decisions. Recovery copies are historical evidence and do not replace the current implementation.

## Storage before/after

| Category | Before | After | Change |
|---|---:|---:|---:|
| Ubuntu-24.04 GREENS content, excluding Git metadata | 29.330 GB | 7.336 GB | 21.993 GB removed |
| Attempt04-Recovery GREENS content, excluding Git metadata | 13.231 GB | 7.195 GB | 6.036 GB removed |
| Compressed archives on D | 0 | 3.820 GB | 16 verified archives |
| Recovery duplicate runs | 5.948 GB | 0 | 8 trees removed |

Net logical reduction after compressed archives and their external manifests: 24,205,164,320 bytes. Host VHDX allocation remains separate; see [the storage report](STORAGE_REDUCTION_REPORT.md).

## Files archived

16 verified tar.gz archives (15,007 regular files): 22.081 GB original to 3.820 GB compressed, stored under `D:/GREENS_ARCHIVES/physical_validation` and `D:/GREENS_ARCHIVES/openram`. Two archives preserve empty historical OpenRAM directories. Full member counts/types/links/sizes/SHA256 and archive hashes were verified. Public member manifests plus [archives/MANIFEST.csv](../archives/MANIFEST.csv) support independent verification.

## Files removed

Only verified archived historical run originals and eight exact duplicate run trees were removed. Each passed through quarantine and a second content comparison. No uncertain source, publication copy, canonical frozen result, tool installation, PDK, unrelated PACT resource or VHDX was deleted.

## Deduplication

Eight recovery run trees, 5,948,489,791 bytes, matched their primary archives member-for-member. [GREENS_DEDUPLICATION_MAP.csv](GREENS_DEDUPLICATION_MAP.csv) records all executed archive replacements and duplicate removals. Source imports with identical SHA256 were published once. Frozen canonical path duplicates and historical Windows checkouts remain, including generated ICCAD grids and publication drafts. They require further ownership/content review or a compatibility-preserving artifact migration.

## Documentation overhaul

README and documentation index rewritten around current scope; 14 focused guides cover architecture, supported ECCs, reliability/Qcrit, ESII/NESII/GS/EPC, optimization, advisory ML, physical flows, reproduction, campaign history and negative results. Current generated status block retained. Citation points to the repository's verified current owner. Ignore rules prevent new caches, environments, scratch/activity outputs and binary archives from entering Git.

## Physical-validation documentation

Distinguishes 192 model-only registry scenarios, inherited matched v3.2 SRAM22/OpenROAD runs, ten fresh 10 ns v3.3 timing runs and 46 E5 logic-power observations. No complete SRAM energy, silicon reliability, Qcrit qualification, signoff or absolute SKY130 lifecycle-carbon claim is introduced. `NO_GLOBAL_WINNER_QUALIFIED` remains explicit.

## OpenRAM status documentation

Pinned OpenRAM 1.2.48 attempt remains blocked: 256x72 target, timeout/exit 137, partial geometry and incomplete qualified macro views/DRC/LVS/characterization. Recovered helpers and negative evidence are preserved. No fresh compiler/physical campaign was launched.

## SRAM22 status documentation

Documents inherited 256x64 and 256x8 views, composed macro boundaries, provenance, common flow-stage bypass and the distinction between frozen physical evidence and freshly compiler-generated OpenRAM qualification.

## Reproducibility

114 missing published files (265,296,049 bytes) were restored from public objects without overwriting existing source. Main/history packs were refetched after initial missing-object damage. Dependency revisions and clean/dirty status are recorded in [DEPENDENCY_PROVENANCE.json](DEPENDENCY_PROVENANCE.json); no tool modification was lost. Archives can be verified with `scripts/verify_greens_archive.py` and extracted into a separate campaign restoration directory. The hash-manifest checkout rule now matches the existing CRLF generator; scientific artifact contents and hashes were not edited.

## Validation

`make`: PASS. `make test`: PASS (490 Python tests plus native unit/selector checks). `python3 -m pytest -q`: PASS (729 tests). Artifact/reference audit and 14 new-guide Markdown links passed. The two historical working-tree scope validators and v3.3 builder determinism test pass after index refresh and the targeted manifest checkout rule. No validator was relaxed. Windows `python3` is a session-local function invoking installed Python 3.12.5 at D:/Python/python.exe.



GitHub CI on the first preservation commit failed: shallow history prevented historical tree comparisons, Windows checkout rejected long artifact paths, frozen logs/SVGs changed line endings on Linux, and `asic_tb_bch_run` failed. CI now fetches full history and enables Windows long paths; 85 explicitly hash-bound dated text/SVG paths use verified checkout rules: 67 CRLF, two raw mixed payloads, and 16 LF preimages with opt-in exact mixed-newline restoration. CI invokes the new explicit restoration flags after checkout. No frozen payload or hash was changed. The remaining legacy generic BCH(63,51) bench failure reproduces with local Icarus: `bch double-bit correction failed` at `asic/tb/tb_bch.sv:21`. It is preserved in [BCH_RTL_CI_NEGATIVE_RESULT.json](BCH_RTL_CI_NEGATIVE_RESULT.json), distinct from the primitive/shortened registry implementations. The PR remains unmerged while this CI failure persists; an RTL behavior change requires a separate explicit scope.

## Quarantine

22,504 regular files were staged, rehashed and removed only after an intact verified replacement existed. Per-file original/quarantine paths and SHA256 are in [quarantine_manifest.csv](quarantine_manifest.csv). WSL staging paths live under `/var/lib/GREENS_CLEANUP_QUARANTINE/2026-10-08` within the F-hosted guest envelopes. `D:/GREENS_CLEANUP_QUARANTINE/receipts` holds operation receipts. No file data remain in quarantine.

## Remaining risks

590 offline/recall-on-data-access files across six old IIITD source copies cannot be scientifically compared until cloud content is available. Large retained Windows artifacts have metadata-only audits. The unregistered 23.702 GB pre-move VHDX was not mounted; its contents may include unique source or unrelated material. Nine historical tag objects remain unavailable. Frozen canonical duplicate paths and tool dependencies remain intentionally intact. Inaccessible Windows system/account directories and unrelated installations were excluded. These limits prohibit a complete classification.

## Largest remaining artifacts

Registered WSL envelopes (about 91.179 and 48.426 GB), the 23.702 GB offline backup and swap remain; pinned dependency views dominate the remaining inspected guest files. See [LARGEST_REMAINING_FILES.md](LARGEST_REMAINING_FILES.md) for exact sizes.

## Final machine layout

C: canonical GREENS checkout, three managed historical checkouts, six protected cloud source copies and publication documents. D: verified compressed archives/member manifests and quarantine receipts. E/G: inspected; no GREENS mutation. F: two registered WSL systems with run data reduced, protected pre-move backup and active swap. Unrelated projects/resources remain in their original locations.
