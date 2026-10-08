# History bloat recommendation

No public history was rewritten. Current tracked logical content totals 11,030,387,276 bytes over 10,655 paths. Exact duplicate paths account for 5,533,945,433 logical bytes; Git already shares identical blob objects, so this is not an estimate of history savings.

Large GDS/ODB/VVP/SPEF and raw results are frozen campaign inputs/outputs with hash and path consumers. Removing them from current Git requires an explicit artifact migration: release/archive storage, stable download/restoration scripts, compact input/result/provenance manifests, and validation of every reference. That migration is outside a compatibility-preserving cleanup.

An optional future `git filter-repo` plan should start with a full recoverable mirror, a reviewed path/blob list, a test rewrite into a separate clone, comparison of packed size before/after, and migration of tags/commit citations/forks/PRs. Publish replacement artifact references first. Coordinate all consumers before any approved public rewrite. Expected packed savings remain unmeasured; the initial missing pack cannot serve as a valid baseline. This campaign performs no force-push.
