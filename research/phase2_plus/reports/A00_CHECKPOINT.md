# A00 checkpoint

The local research branch and fetched GitHub research branch both pointed to
`967015e1501bf237800f8851bd78ea12f36938af` at campaign initialization. The
worktree had no preexisting changes. The fetched main branch still pointed to
`f193b9902792c798dde57534137e0075dab0aff4`. The historical scientific-input
commit `8cf245ac6ac8cb9b010c073d439f04eb204d48a1` is present in Git.

The [Phase II validator](../../phase2/scripts/validate_phase2.py) verified all
189 audited baseline files. The [baseline manifest](../../phase2/baseline_manifest.json)
SHA-256 is `b3b96bfa26396ab15a7cc57fa2327005b1a8ce82aeacc148dec86c7a95d7052f`.
Phase II tests yielded **13 passed, one skipped**. The skip requires Windows
symlink privilege. The two pre-existing Hsiao encoder and syndrome LF/CRLF
conflicts are still exact-byte identity failures for the historical contracts.
The Phase II audit established that the frozen expected hashes correspond to
the CRLF representations. The working files and contracts are intact.
[Phase II report](../../phase2/PHASE_II_RESEARCH_REPORT.md) ·
[Byte audit](../../phase2/repository_audit.md)

The worktree remains a partial, sparse checkout. The active DATE evidence and
Phase II package are present. The full archives, ISCAS campaign, generated
public documentation inputs, and some software data/modules are omitted. Git
contains the selected ISCAS blobs, and A03 uses the existing checkout attributes
when materializing a bounded read-only input snapshot.

| Measured at initialization | Free bytes | Free GiB |
|---|---:|---:|
| Workspace drive | 27,994,062,848 | 26.07 |
| Campaign drive | 83,306,139,648 | 77.58 |

The existing AutonomousEDA WSL2 instance exposed four virtual CPUs and
approximately 3.30 GiB of then-available memory, with no usable swap. Mount
space was measured separately from guest filesystem capacity. Native Python
3.12.5, make, g++, Yosys and Icarus were present. WSL provided the existing
Icarus cache and the digest-pinned ORFS image. OpenROAD identifies its version
as `unknown` inside that image. The observable, pinned identifier is the
container digest, with an independently hashed TT Liberty.

The Phase II+ campaign initialized at **2026-11-28 14:30:31 UTC** and expires
at **2026-11-29 14:30:31 UTC**. The full runtime checkpoint keeps fractional
seconds, command exits, storage samples, and the private experiment location.
Historical four-hour Phase II runs retain their own completed or blocked
status and original deadlines.

The root native build passed. Root `make test`, pytest, artifact and
documentation checks encountered omitted calibration, support modules and
generated documentation inputs. The root ISCAS command also encountered the
sparse import omission. A03 subsequently ran the unchanged full ISCAS
reproduction successfully from the selective snapshot.
