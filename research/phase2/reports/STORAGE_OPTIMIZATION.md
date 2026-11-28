# Storage optimization and retention

The execution reused an existing WSL2 distribution, ORFS image, native Python/Git/scientific packages, and cached Linux simulator. New installed toolchain/PDK dependency space: **0 bytes**. Public two-cell qualification source: **22,492 bytes**. There is one research checkout, and the original baseline has not been duplicated into a new physical campaign.

Twenty-four generated per-bit activity JSON summaries were losslessly compressed: 24,348,899 original bytes became 222,822 compressed bytes, saving **24,126,077 bytes (23.01 MiB)**. Every compressed file was decompressed and compared byte-for-byte before its uncompressed duplicate was removed. SHA-256, byte lengths and the explicit removal decision are in `manifests/compression.json`. No raw waveform was discarded. All small qualification VCDs, including failures and negative controls, remain complete.

The large development summaries include the testbench's filename-vector variables, which are not physical circuit nets. They are excluded from the scientific event comparisons by exact signal identity. A production dump must restrict scope to circuit/transaction signals before streaming; the current small parser test is not a claim of production-scale memory or power-import qualification.

Content-addressed references in `manifests/artifact_references.json` map SHA-256 values to the existing baseline paths and missing archive-member identities. A/B/C status rows refer to shared physical identities rather than separate copied netlists/parasitics. Measured duplicate-file deletion savings are **0 bytes**; avoided hypothetical copies are not booked as measured savings.

Streaming statistics were validated against a complete-event oracle on a retained waveform. **Production waveform bytes saved: unavailable**, because no production run was admitted. No hypothetical 100,000-operation VCD size is reported as measured savings. The parser can consume a pipe and retain per-bit directions, occupancy/X/Z duration, positive pulse segments, aliases and bounded pulse samples. Full power-tool activity-format compatibility remains open; a toggle summary is not automatically suitable for OpenSTA.

Peak experimental-storage monitoring was sampled, not continuous. `processed/storage_summary.json` reports exact retained Phase II file sizes at the final sample and the known 24.35 MB pre-compression summary volume. Acquisition overhead is listed separately in the storage audit. No claim of an exact unobserved instantaneous peak is made.

Deferred work is caused primarily by missing physical evidence and simulator capability, not a demonstrated shortage of disk. More disk would not repair annotation validity. The five-seed physical expansion, trace convergence, per-net capacitance/event joins, workload-energy sensitivity and rare-error energy measurements remain blocked. No scientific check was weakened to fit storage.

The cleanup utility is confined to explicitly classified scratch files from COMPLETE runs with verified retained artifacts. It preserves unknown files, incomplete recovery data, and unique evidence. It was tested on disposable test files only. Existing Git temporary packs, WSL disks, user caches, PDKs and repositories were not manually cleaned.
