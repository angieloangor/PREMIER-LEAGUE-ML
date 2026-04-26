from __future__ import annotations

from .dataops import build_data_artifacts
from .dashboard import build_dashboard_payload, export_outputs
from .legacy_models import train_match_models, train_xg_models


def run_pipeline() -> dict[str, object]:
    data_artifacts = build_data_artifacts()
    players = data_artifacts["players"]
    matches = data_artifacts["matches"]
    event_stats = data_artifacts["event_stats"]
    shots = data_artifacts["shots"]
    match_features = data_artifacts["match_features"]
    xg_results = train_xg_models(shots)
    match_results = train_match_models(match_features)
    payload = build_dashboard_payload(players, matches, event_stats, xg_results, match_results)
    exported = export_outputs(payload)
    return {"payload": payload, "exported": exported, "data_artifacts": data_artifacts}


def main() -> None:
    results = run_pipeline()
    payload = results["payload"]
    print("Pipeline del taller ejecutado correctamente.")
    print(f"Accuracy CV modelo: {payload['match_accuracy']:.2f}%")
    print(f"Benchmark Bet365 CV: {payload['project_summary']['benchmark_bet365']:.2f}%")
    print(f"AUC xG logística: {payload['xg_metrics']['auc_roc']:.4f}")
    print(f"Dashboard JSON: {results['exported']['dashboard_json']}")
