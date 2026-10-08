# ML advisory

ML stays under `ml/` and is explicitly enabled. The deterministic selector remains default/baseline. Training records seeds, features, metrics, thresholds, model cards, and dataset provenance.

Low confidence or OOD score above the stored threshold selects baseline fallback. OOD uses feature z-scores with the documented feature scope. Advisory prediction does not supply missing physical evidence or qualify unseen technologies.

Existing suites cover deterministic training, OOD fallback, train-to-predict smoke, holdout/drift, and golden CLI output. Cleanup does not retrain models or alter thresholds/schemas. See [ML design](../ml_design.md), [drift policy](../drift_policy.md), and `tests/python/test_ml_integration.py`.
