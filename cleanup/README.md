# GREENS storage campaign

The inventory and CSV audits are snapshots, not live filesystem instructions. Decisions use repository identity, size, SHA256, and public Git object membership. System installations, PDKs, unrelated PACT resources, credentials, and uncertain ownership are retained. Broad keyword matches alone do not justify removal.

`LOCAL_TO_GITHUB_AUDIT.csv` records reviewed project files. `ADD_TO_GITHUB` rows point to byte-preserved historical recovery; duplicate imports point to the same destination. `already_on_github=true` means an exact current SHA256 or a raw/CRLF-normalized Git blob occurs in the fetched public main history. It does not mean the file is current active source. Vendor trees are audited by revision/status in `DEPENDENCY_PROVENANCE.json`, not reimported.

The canonical public snapshot at start is `68fd3e7020966cf74041dec0780d7e8b285ce31a`. Initial Git objects were missing; a public re-fetch recovered the reachable main objects. 114 absent published files (265,296,049 bytes) were restored without overwriting present files. Nine historical tag objects are unavailable remotely; their reference names/IDs are preserved locally.

Archive creation and file/tree removals happen only after unique source is published and archive member counts/content hashes verify. `archives/MANIFEST.csv` identifies external archive paths and verification; quarantine and deduplication maps record actual executed operations, never just proposed candidates. Empty CSV bodies mean no operations have yet been executed.

Footprints distinguish logical regular-file sizes, shared Git objects, and host VHDX envelopes. Linux contents must not be added again to the host VHDX size. Host disk reclamation differs from freeing ext4 blocks inside a still-allocated VHDX.
