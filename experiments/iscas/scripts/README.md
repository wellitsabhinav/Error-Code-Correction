# GREENS ISCAS analysis entry points

- [scripts/reproduce_iscas.py](../../../scripts/reproduce_iscas.py): maintained reviewer entry point; verifies evidence and writes separate tables/figure. Run from the repository root.
- [Frozen v3.3 collector](../../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/finalize_executed_campaign.py): existing normalization reused read-only by the reviewer entry point. Its full finalization routine writes campaign outputs and must not be run against frozen evidence during review.
- [Physical execution scripts](../../../campaigns/iscas_sustainability_extension/green_v3_3_activity_complete_e5/scripts/): historical machinery; inspect for regeneration design, preserve the sealed queue/deadline.

[Exact reproduction instructions](../reproduction.md) · [Claim map](../claims.md) · [Root instructions](../../../AGENTS.md)
