from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectFromModel
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, TimeSeriesSplit
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline as SklearnPipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from ..config import OUTPUTS_DIR
from ..features import build_candidate_indices
from .base import ModelSpec
from .feature_sets import CANDIDATE_INDEX_COLUMNS, available_numeric_features, resolve_feature_columns
from .registry import get_model_spec
from .select_best_model import rank_regressor_bundles

try:
    import torch
except ImportError:  # pragma: no cover - depends on local environment
    torch = None

try:
    from imblearn.over_sampling import SMOTE
    from imblearn.pipeline import Pipeline as ImbPipeline
except ImportError:  # pragma: no cover - depends on local environment
    SMOTE = None
    ImbPipeline = None


def _split_time_ordered_frame(dataframe: pd.DataFrame, holdout_ratio: float = 0.2):
    split_index = max(int(len(dataframe) * (1 - holdout_ratio)), 1)
    if split_index >= len(dataframe):
        split_index = len(dataframe) - 1
    return dataframe.iloc[:split_index].copy(), dataframe.iloc[split_index:].copy()


def _rmse(y_true, y_pred) -> float:
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


@dataclass
class RunPlan:
    regressor_name: str
    classifier_name: str
    feature_mode: str

    @property
    def slug(self) -> str:
        return f"{self.regressor_name}+{self.classifier_name}+{self.feature_mode}"


@dataclass
class AdvancedStage2Plan:
    generator_run_name: str
    classifier_name: str
    feature_mode: str

    @property
    def slug(self) -> str:
        return f"{self.generator_run_name}__{self.classifier_name}+{self.feature_mode}"


class MatchPredictorAutoML:
    def __init__(
        self,
        match_features: pd.DataFrame,
        output_dir: Path | None = None,
        holdout_ratio: float = 0.2,
        cv_splits: int = 5,
        random_state: int = 42,
    ) -> None:
        self.match_features = match_features.sort_values(["kickoff", "id"]).reset_index(drop=True)
        self.output_dir = Path(output_dir or (OUTPUTS_DIR / "model_runs"))
        self.holdout_ratio = holdout_ratio
        self.cv_splits = cv_splits
        self.random_state = random_state

    def plan_runs(
        self,
        regressors: list[str],
        classifiers: list[str],
        feature_modes: list[str],
        explicit_pairs: list[tuple[str, str]] | None = None,
    ) -> list[RunPlan]:
        if explicit_pairs is not None:
            return [
                RunPlan(regressor_name=reg, classifier_name=clf, feature_mode=feature_mode)
                for reg, clf in explicit_pairs
                for feature_mode in feature_modes
            ]

        return [
            RunPlan(regressor_name=regressor_name, classifier_name=classifier_name, feature_mode=feature_mode)
            for regressor_name in regressors
            for classifier_name in classifiers
            for feature_mode in feature_modes
        ]

    def run(
        self,
        regressors: list[str],
        classifiers: list[str],
        goal_feature_set: str | list[str] = "goals_default",
        winner_feature_set: str | list[str] = "winner_default",
        explicit_pairs: list[tuple[str, str]] | None = None,
        feature_modes: list[str] | None = None,
        search_iterations: int = 8,
        include_stage1_prediction: bool = True,
        smote: bool = True,
        advance_modeling: bool = False,
        stage1_feature_set: str | list[str] = "history_only",
        stage1_target_set: str | list[str] = "candidate_indices",
        stage1_top_k: int = 3,
        stage1_min_r2: float = 0.15,
        include_all: bool = False,
        session_name: str | None = None,
    ) -> dict[str, object]:
        effective_feature_modes = feature_modes or ["normal", "extra", "lasso_selected", "poly2_lasso"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_slug = session_name or f"match_predictor_{timestamp}"
        session_dir = self.output_dir / session_slug
        session_dir.mkdir(parents=True, exist_ok=True)

        if advance_modeling:
            return self._run_advanced(
                regressors=regressors,
                classifiers=classifiers,
                winner_feature_set=winner_feature_set,
                feature_modes=effective_feature_modes,
                search_iterations=search_iterations,
                smote=smote,
                stage1_feature_set=stage1_feature_set,
                stage1_target_set=stage1_target_set,
                stage1_top_k=stage1_top_k,
                stage1_min_r2=stage1_min_r2,
                include_all=include_all,
                session_slug=session_slug,
                session_dir=session_dir,
            )

        plans = self.plan_runs(
            regressors,
            classifiers,
            feature_modes=effective_feature_modes,
            explicit_pairs=explicit_pairs,
        )

        print(f"Planned runs: {len(plans)}")
        print(f"Classification SMOTE: {'on' if smote else 'off'}")
        for plan in plans:
            reg_spec = get_model_spec(plan.regressor_name)
            clf_spec = get_model_spec(plan.classifier_name)
            print(
                f"- {plan.slug}: "
                f"{reg_spec.search_space_size} regression combos, "
                f"{clf_spec.search_space_size} classification combos"
            )

        results: list[dict[str, object]] = []
        for index, plan in enumerate(plans, start=1):
            print(f"[{index}/{len(plans)}] Running {plan.slug}")
            run_summary = self._execute_run(
                plan=plan,
                session_dir=session_dir,
                goal_feature_set=goal_feature_set,
                winner_feature_set=winner_feature_set,
                search_iterations=search_iterations,
                include_stage1_prediction=include_stage1_prediction,
                smote=smote,
            )
            results.append(run_summary)
            print(f"    Stage 1 Regression")
            print(
                f"      mean CV R2:       {run_summary['regressor']['cv_metrics']['mean_cv_r2']:.4f}"
                f"    mean CV RMSE:       {run_summary['regressor']['cv_metrics']['mean_cv_rmse']:.4f}"
            )
            print(
                f"      train RMSE:       {run_summary['regression_metrics']['train']['rmse']:.4f}"
                f"    test RMSE:          {run_summary['regression_metrics']['test']['rmse']:.4f}"
            )
            print(
                f"      train MAE:        {run_summary['regression_metrics']['train']['mae']:.4f}"
                f"    test MAE:           {run_summary['regression_metrics']['test']['mae']:.4f}"
            )
            print("")
            print(f"    Stage 2 Classification")
            print(
                f"      mean CV accuracy: {run_summary['classifier']['cv_metrics']['mean_cv_accuracy']:.4f}"
                f"    mean CV F1:         {run_summary['classifier']['cv_metrics']['mean_cv_f1_weighted']:.4f}"
            )
            print(
                f"      train accuracy:   {run_summary['classifier_metrics']['train']['accuracy']:.4f}"
                f"    test accuracy:      {run_summary['classifier_metrics']['test']['accuracy']:.4f}"
            )
            print(
                f"      train F1:         {run_summary['classifier_metrics']['train']['f1_weighted']:.4f}"
                f"    test F1:            {run_summary['classifier_metrics']['test']['f1_weighted']:.4f}"
            )
            print("")

        summary_json = session_dir / "experiment_report.json"
        summary_csv = session_dir / "experiment_report.csv"
        summary_payload = {
            "session": session_slug,
            "generated_at": datetime.now().isoformat(),
            "goal_feature_set": goal_feature_set,
            "winner_feature_set": winner_feature_set,
            "feature_modes": effective_feature_modes,
            "include_stage1_prediction": include_stage1_prediction,
            "smote": smote,
            "advance_modeling": False,
            "runs": results,
        }
        summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
        pd.DataFrame([self._flatten_run_summary(item) for item in results]).to_csv(summary_csv, index=False)
        return summary_payload

    def _run_advanced(
        self,
        regressors: list[str],
        classifiers: list[str],
        winner_feature_set,
        feature_modes: list[str],
        search_iterations: int,
        smote: bool,
        stage1_feature_set,
        stage1_target_set,
        stage1_top_k: int,
        stage1_min_r2: float,
        include_all: bool,
        session_slug: str,
        session_dir: Path,
    ) -> dict[str, object]:
        ordered = self.match_features.copy()
        train_df, test_df = _split_time_ordered_frame(ordered, holdout_ratio=self.holdout_ratio)
        stage1_feature_columns = resolve_feature_columns(ordered, stage1_feature_set, stage="regression")
        candidate_indices = build_candidate_indices(ordered)
        ordered = pd.concat([ordered.reset_index(drop=True), candidate_indices.reset_index(drop=True)], axis=1)
        train_df, test_df = _split_time_ordered_frame(ordered, holdout_ratio=self.holdout_ratio)
        stage1_target_columns = resolve_feature_columns(ordered, stage1_target_set, stage="regression")
        if not stage1_feature_columns:
            raise ValueError("No se encontraron columnas ex ante históricas para la etapa 1 avanzada.")
        if not stage1_target_columns:
            raise ValueError("No se encontraron índices candidatos para la etapa 1 avanzada.")

        stage1_dir = session_dir / "stage1_feature_generators"
        stage2_dir = session_dir / "stage2_classifier_runs"
        stage1_dir.mkdir(parents=True, exist_ok=True)
        stage2_dir.mkdir(parents=True, exist_ok=True)

        print("Advance modeling: on")
        print(f"Stage 1 feature generators planned: {len(regressors)}")
        print(f"Stage 1 candidate metrics: {len(stage1_target_columns)}")
        print(f"Stage 2 classifiers planned: {len(classifiers)}")
        print(f"Stage 2 feature modes: {feature_modes}")
        print(f"Classification SMOTE: {'on' if smote else 'off'}")
        print(f"Include all best generated indices: {'on' if include_all else 'off'}")

        stage1_runs: list[dict[str, Any]] = []
        selected_generators: list[dict[str, Any]] = []
        for metric_index, target_metric in enumerate(stage1_target_columns, start=1):
            metric_dir = stage1_dir / target_metric
            metric_dir.mkdir(parents=True, exist_ok=True)
            print(f"[metric {metric_index}/{len(stage1_target_columns)}] Stage 1 target: {target_metric}")
            for regressor_index, regressor_name in enumerate(regressors, start=1):
                print(
                    f"  [stage1 {regressor_index}/{len(regressors)}] Training {regressor_name} for {target_metric}"
                )
                summary = self._execute_feature_generator_run(
                    regressor_name=regressor_name,
                    train_df=train_df,
                    test_df=test_df,
                    feature_columns=stage1_feature_columns,
                    target_metric=target_metric,
                    search_iterations=search_iterations,
                    output_dir=metric_dir,
                )
                stage1_runs.append(summary)
                print(
                    f"      mean CV R2:  {summary['regressor']['cv_metrics']['mean_cv_r2']:.4f}"
                    f"    test R2:     {summary['regression_metrics']['test']['r2']:.4f}"
                )

            metric_selected = rank_regressor_bundles(
                metric_dir,
                top_k=stage1_top_k,
                metric_name=target_metric,
                min_test_r2=stage1_min_r2,
            )
            if not metric_selected:
                print(f"  No stage1 generator passed R2>{stage1_min_r2:.2f} for {target_metric}. Skipping.")
                continue
            print(f"  Selected generators for {target_metric}: {len(metric_selected)}")
            for item in metric_selected:
                print(
                    f"  - rank {item['rank']}: {item['run_name']} "
                    f"(cv_r2={item['cv_r2']:.4f}, test_r2={item['test_r2']:.4f})"
                )
            selected_generators.extend(metric_selected)

        best_generators_by_metric = self._select_best_generator_per_metric(selected_generators)

        stage2_plans = [
            {
                "plan_type": "single_metric",
                "target_metric": item["target_metric"],
                "generator_run_name": item["run_name"],
                "generator_entries": [item],
                "classifier_name": classifier_name,
                "feature_mode": feature_mode,
            }
            for item in selected_generators
            for classifier_name in classifiers
            for feature_mode in feature_modes
        ]
        if include_all and best_generators_by_metric:
            stage2_plans.extend(
                {
                    "plan_type": "include_all",
                    "target_metric": "__all__",
                    "generator_run_name": "include_all_best_metrics",
                    "generator_entries": best_generators_by_metric,
                    "classifier_name": classifier_name,
                    "feature_mode": feature_mode,
                }
                for classifier_name in classifiers
                for feature_mode in feature_modes
            )
        print(f"Planned advanced stage2 runs: {len(stage2_plans)}")

        stage2_runs: list[dict[str, Any]] = []
        for index, plan in enumerate(stage2_plans, start=1):
            generator_bundles = [
                self._load_saved_bundle(
                    bundle_dir=Path(generator_entry["bundle_dir"]),
                    summary_filename="run_summary.json",
                    artifact_key="regressor",
                )
                for generator_entry in plan["generator_entries"]
            ]
            slug = self._advanced_stage2_slug(plan)
            print(f"[stage2 {index}/{len(stage2_plans)}] Running {slug}")
            summary = self._execute_advanced_stage2_run(
                plan=plan,
                generator_bundles=generator_bundles,
                train_df=train_df,
                test_df=test_df,
                winner_feature_set=winner_feature_set,
                search_iterations=search_iterations,
                smote=smote,
                output_dir=stage2_dir,
            )
            stage2_runs.append(summary)
            print(
                f"    generated metrics:   {len(summary['generator_models'])}"
                f"    generator test R2:   {summary['generator_model']['test_r2']:.4f}"
                f"    mean CV accuracy:    {summary['classifier']['cv_metrics']['mean_cv_accuracy']:.4f}"
            )
            print(
                f"    test accuracy:       {summary['classifier_metrics']['test']['accuracy']:.4f}"
                f"    test F1:             {summary['classifier_metrics']['test']['f1_weighted']:.4f}"
            )

        stage1_report_json = stage1_dir / "stage1_report.json"
        stage1_report_csv = stage1_dir / "stage1_report.csv"
        stage2_report_json = stage2_dir / "stage2_report.json"
        stage2_report_csv = stage2_dir / "stage2_report.csv"

        stage1_payload = {
            "session": session_slug,
            "run_type": "advanced_stage1_feature_generators",
            "generated_at": datetime.now().isoformat(),
            "stage1_feature_set": stage1_feature_set,
            "stage1_target_set": stage1_target_set,
            "runs": stage1_runs,
        }
        stage2_payload = {
            "session": session_slug,
            "run_type": "advanced_stage2_classification",
            "generated_at": datetime.now().isoformat(),
            "winner_feature_set": winner_feature_set,
            "feature_modes": feature_modes,
            "smote": smote,
            "include_all": include_all,
            "best_generators_by_metric": best_generators_by_metric,
            "selected_generators": selected_generators,
            "runs": stage2_runs,
        }
        stage1_report_json.write_text(json.dumps(stage1_payload, indent=2), encoding="utf-8")
        stage2_report_json.write_text(json.dumps(stage2_payload, indent=2), encoding="utf-8")
        pd.DataFrame([self._flatten_stage1_summary(item) for item in stage1_runs]).to_csv(stage1_report_csv, index=False)
        pd.DataFrame([self._flatten_advanced_stage2_summary(item) for item in stage2_runs]).to_csv(stage2_report_csv, index=False)

        summary_json = session_dir / "experiment_report.json"
        summary_payload = {
            "session": session_slug,
            "generated_at": datetime.now().isoformat(),
            "advance_modeling": True,
            "smote": smote,
            "stage1_feature_set": stage1_feature_set,
            "stage1_target_set": stage1_target_set,
            "stage1_top_k": stage1_top_k,
            "stage1_min_r2": stage1_min_r2,
            "include_all": include_all,
            "best_generators_by_metric": best_generators_by_metric,
            "selected_generators": selected_generators,
            "stage1_runs": stage1_runs,
            "stage2_runs": stage2_runs,
            "artifacts": {
                "stage1_report_json": str(stage1_report_json),
                "stage1_report_csv": str(stage1_report_csv),
                "stage2_report_json": str(stage2_report_json),
                "stage2_report_csv": str(stage2_report_csv),
            },
        }
        summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
        return summary_payload

    def _execute_feature_generator_run(
        self,
        regressor_name: str,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        feature_columns: list[str],
        target_metric: str,
        search_iterations: int,
        output_dir: Path,
    ) -> dict[str, Any]:
        reg_spec = get_model_spec(regressor_name)
        run_name = f"{regressor_name}+{target_metric}+feature_generator"
        run_dir = output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        reg_search = self._fit_search(
            dataframe=train_df,
            feature_columns=feature_columns,
            target_column=target_metric,
            spec=reg_spec,
            search_iterations=search_iterations,
            feature_mode="normal",
        )
        best_regressor = reg_search.best_estimator_

        train_metrics = self._evaluate_regressor(
            best_regressor,
            train_df[feature_columns],
            train_df[target_metric],
        )
        test_metrics = self._evaluate_regressor(
            best_regressor,
            test_df[feature_columns],
            test_df[target_metric],
        )

        reg_model_path = run_dir / f"regressor.{self._artifact_extension(reg_spec)}"
        self._save_model(best_regressor, reg_model_path, reg_spec)
        reg_search_results_path = run_dir / "regression_search_results.csv"
        pd.DataFrame(reg_search.cv_results_).to_csv(reg_search_results_path, index=False)
        reg_cv_metrics = self._extract_best_cv_metrics(reg_search, stage="regression")

        run_summary = {
            "run_type": "feature_generator",
            "run_name": run_name,
            "target_metric": target_metric,
            "feature_mode": "normal",
            "regressor": {
                "name": reg_spec.key,
                "best_params": reg_search.best_params_,
                "best_cv_score": float(reg_search.best_score_),
                "cv_metrics": reg_cv_metrics,
                "feature_columns": feature_columns,
                "target_columns": [target_metric],
                "artifact_path": str(reg_model_path),
            },
            "regression_metrics": {
                "train": train_metrics,
                "test": test_metrics,
            },
            "search_results": {
                "regression_csv": str(reg_search_results_path),
            },
        }
        (run_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
        return run_summary

    def _execute_advanced_stage2_run(
        self,
        plan: dict[str, Any],
        generator_bundles: list[dict[str, Any]],
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        winner_feature_set,
        search_iterations: int,
        smote: bool,
        output_dir: Path,
    ) -> dict[str, Any]:
        clf_spec = get_model_spec(plan["classifier_name"])
        run_name = self._advanced_stage2_slug(plan)
        run_dir = output_dir / run_name
        run_dir.mkdir(parents=True, exist_ok=True)

        generator_models_summary = []
        train_generated_frames: list[pd.DataFrame] = []
        test_generated_frames: list[pd.DataFrame] = []
        generated_feature_columns: list[str] = []
        for generator_bundle in generator_bundles:
            generator_model = generator_bundle["model"]
            stage1_feature_columns = generator_bundle["summary"]["regressor"]["feature_columns"]
            target_columns = generator_bundle["summary"]["regressor"]["target_columns"]
            train_pred = np.asarray(generator_model.predict(train_df[stage1_feature_columns]))
            test_pred = np.asarray(generator_model.predict(test_df[stage1_feature_columns]))
            train_generated, bundle_generated_feature_columns = self._prediction_frame(train_pred, target_columns)
            test_generated, _ = self._prediction_frame(test_pred, target_columns)
            train_generated_frames.append(train_generated)
            test_generated_frames.append(test_generated)
            generated_feature_columns.extend(bundle_generated_feature_columns)
            generator_models_summary.append(
                {
                    "run_name": generator_bundle["summary"]["run_name"],
                    "name": generator_bundle["summary"]["regressor"]["name"],
                    "artifact_path": generator_bundle["summary"]["regressor"]["artifact_path"],
                    "feature_columns": stage1_feature_columns,
                    "target_columns": target_columns,
                    "generated_feature_columns": bundle_generated_feature_columns,
                    "cv_r2": generator_bundle["summary"]["regressor"]["cv_metrics"]["mean_cv_r2"],
                    "test_r2": generator_bundle["summary"]["regression_metrics"]["test"]["r2"],
                    "target_metric": generator_bundle["summary"]["target_metric"],
                }
            )

        train_generated = pd.concat(train_generated_frames, axis=1)
        test_generated = pd.concat(test_generated_frames, axis=1)

        classifier_train = pd.concat([train_df.reset_index(drop=True), train_generated], axis=1)
        classifier_test = pd.concat([test_df.reset_index(drop=True), test_generated], axis=1)
        classifier_columns = self._resolve_advanced_stage2_columns(
            classifier_train,
            winner_feature_set=winner_feature_set,
            feature_mode=plan["feature_mode"],
            generated_feature_columns=generated_feature_columns,
        )

        clf_search = self._fit_search(
            dataframe=classifier_train.assign(result_code=train_df["result_code"].to_numpy()),
            feature_columns=classifier_columns,
            target_column="result_code",
            spec=clf_spec,
            search_iterations=search_iterations,
            feature_mode=plan["feature_mode"],
            smote=smote,
        )
        best_classifier = clf_search.best_estimator_

        clf_train_metrics = self._evaluate_classifier(
            best_classifier,
            classifier_train[classifier_columns],
            train_df["result_code"],
        )
        clf_test_metrics = self._evaluate_classifier(
            best_classifier,
            classifier_test[classifier_columns],
            test_df["result_code"],
        )

        clf_model_path = run_dir / f"classifier.{self._artifact_extension(clf_spec)}"
        self._save_model(best_classifier, clf_model_path, clf_spec)
        clf_search_results_path = run_dir / "classification_search_results.csv"
        pd.DataFrame(clf_search.cv_results_).to_csv(clf_search_results_path, index=False)
        clf_cv_metrics = self._extract_best_cv_metrics(clf_search, stage="classification")
        run_summary = {
            "run_type": "advanced_stage2",
            "run_name": run_name,
            "target_metric": plan["target_metric"],
            "plan_type": plan["plan_type"],
            "feature_mode": plan["feature_mode"],
            "smote": smote,
            "generator_model": generator_models_summary[0],
            "generator_models": generator_models_summary,
            "classifier": {
                "name": clf_spec.key,
                "best_params": clf_search.best_params_,
                "best_cv_score": float(clf_search.best_score_),
                "cv_metrics": clf_cv_metrics,
                "feature_columns": classifier_columns,
                "artifact_path": str(clf_model_path),
            },
            "classifier_metrics": {
                "train": clf_train_metrics,
                "test": clf_test_metrics,
            },
            "search_results": {
                "classification_csv": str(clf_search_results_path),
            },
        }
        (run_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
        return run_summary

    def _execute_run(
        self,
        plan: RunPlan,
        session_dir: Path,
        goal_feature_set,
        winner_feature_set,
        search_iterations: int,
        include_stage1_prediction: bool,
        smote: bool,
    ) -> dict[str, object]:
        reg_spec = get_model_spec(plan.regressor_name)
        clf_spec = get_model_spec(plan.classifier_name)
        run_dir = session_dir / plan.slug
        run_dir.mkdir(parents=True, exist_ok=True)

        ordered = self.match_features.copy()
        train_df, test_df = _split_time_ordered_frame(ordered, holdout_ratio=self.holdout_ratio)

        goal_columns = self._resolve_mode_columns(
            ordered,
            goal_feature_set,
            stage="regression",
            feature_mode=plan.feature_mode,
        )
        winner_columns = self._resolve_mode_columns(
            ordered,
            winner_feature_set,
            stage="classification",
            feature_mode=plan.feature_mode,
        )

        reg_search = self._fit_search(
            dataframe=train_df,
            feature_columns=goal_columns,
            target_column="total_goals",
            spec=reg_spec,
            search_iterations=search_iterations,
            feature_mode=plan.feature_mode,
        )
        best_regressor = reg_search.best_estimator_
        train_goal_pred = best_regressor.predict(train_df[goal_columns])
        test_goal_pred = best_regressor.predict(test_df[goal_columns])

        classifier_train = train_df[winner_columns].copy()
        classifier_test = test_df[winner_columns].copy()
        classifier_columns = winner_columns.copy()
        if include_stage1_prediction:
            classifier_train["stage1_pred_total_goals"] = train_goal_pred
            classifier_test["stage1_pred_total_goals"] = test_goal_pred
            classifier_columns = [*classifier_columns, "stage1_pred_total_goals"]

        clf_search = self._fit_search(
            dataframe=classifier_train.assign(result_code=train_df["result_code"].to_numpy()),
            feature_columns=classifier_columns,
            target_column="result_code",
            spec=clf_spec,
            search_iterations=search_iterations,
            feature_mode=plan.feature_mode,
            smote=smote,
        )
        best_classifier = clf_search.best_estimator_

        reg_train_metrics = self._evaluate_regressor(best_regressor, train_df[goal_columns], train_df["total_goals"])
        reg_test_metrics = self._evaluate_regressor(best_regressor, test_df[goal_columns], test_df["total_goals"])
        clf_train_metrics = self._evaluate_classifier(best_classifier, classifier_train[classifier_columns], train_df["result_code"])
        clf_test_metrics = self._evaluate_classifier(best_classifier, classifier_test[classifier_columns], test_df["result_code"])

        reg_model_path = run_dir / f"regressor.{self._artifact_extension(reg_spec)}"
        clf_model_path = run_dir / f"classifier.{self._artifact_extension(clf_spec)}"
        self._save_model(best_regressor, reg_model_path, reg_spec)
        self._save_model(best_classifier, clf_model_path, clf_spec)

        reg_search_results_path = run_dir / "regression_search_results.csv"
        clf_search_results_path = run_dir / "classification_search_results.csv"
        pd.DataFrame(reg_search.cv_results_).to_csv(reg_search_results_path, index=False)
        pd.DataFrame(clf_search.cv_results_).to_csv(clf_search_results_path, index=False)
        reg_cv_metrics = self._extract_best_cv_metrics(reg_search, stage="regression")
        clf_cv_metrics = self._extract_best_cv_metrics(clf_search, stage="classification")

        run_summary = {
            "run_name": plan.slug,
            "feature_mode": plan.feature_mode,
            "smote": smote,
            "regressor": {
                "name": reg_spec.key,
                "best_params": reg_search.best_params_,
                "best_cv_score": float(reg_search.best_score_),
                "cv_metrics": reg_cv_metrics,
                "feature_columns": goal_columns,
                "artifact_path": str(reg_model_path),
            },
            "classifier": {
                "name": clf_spec.key,
                "best_params": clf_search.best_params_,
                "best_cv_score": float(clf_search.best_score_),
                "cv_metrics": clf_cv_metrics,
                "feature_columns": classifier_columns,
                "artifact_path": str(clf_model_path),
            },
            "regression_metrics": {
                "train": reg_train_metrics,
                "test": reg_test_metrics,
            },
            "classifier_metrics": {
                "train": clf_train_metrics,
                "test": clf_test_metrics,
            },
            "search_results": {
                "regression_csv": str(reg_search_results_path),
                "classification_csv": str(clf_search_results_path),
            },
        }
        (run_dir / "run_summary.json").write_text(json.dumps(run_summary, indent=2), encoding="utf-8")
        return run_summary

    def _fit_search(
        self,
        dataframe: pd.DataFrame,
        feature_columns: list[str],
        target_column: str | list[str],
        spec: ModelSpec,
        search_iterations: int,
        feature_mode: str,
        smote: bool = False,
        multioutput: bool = False,
    ):
        estimator = self._build_pipeline(
            spec,
            stage=spec.stage,
            feature_mode=feature_mode,
            smote=smote,
            multioutput=multioutput,
        )
        param_grid = self._prepare_param_grid(spec, multioutput=multioutput)
        cv = TimeSeriesSplit(n_splits=self.cv_splits)
        scoring, refit = self._scoring_config(spec.stage)

        if spec.search_space_size <= search_iterations:
            search = GridSearchCV(
                estimator=estimator,
                param_grid=param_grid,
                scoring=scoring,
                refit=refit,
                cv=cv,
                n_jobs=1,
                verbose=0,
            )
        else:
            search = RandomizedSearchCV(
                estimator=estimator,
                param_distributions=param_grid,
                n_iter=search_iterations,
                scoring=scoring,
                refit=refit,
                cv=cv,
                n_jobs=1,
                verbose=0,
                random_state=self.random_state,
            )

        search.fit(dataframe[feature_columns], dataframe[target_column])
        return search

    def _extract_best_cv_metrics(self, search, stage: str) -> dict[str, float]:
        row = pd.DataFrame(search.cv_results_).iloc[int(search.best_index_)]
        if stage == "regression":
            return {
                "mean_cv_r2": float(row["mean_test_r2"]),
                "mean_cv_mae": float(-row["mean_test_neg_mae"]),
                "mean_cv_rmse": float(-row["mean_test_neg_rmse"]),
            }
        return {
            "mean_cv_accuracy": float(row["mean_test_accuracy"]),
            "mean_cv_f1_weighted": float(row["mean_test_f1_weighted"]),
        }

    def _build_pipeline(
        self,
        spec: ModelSpec,
        stage: str,
        feature_mode: str,
        smote: bool = False,
        multioutput: bool = False,
    ):
        steps = [("imputer", SimpleImputer(strategy="median"))]
        if feature_mode == "poly2_lasso":
            steps.append(("poly", PolynomialFeatures(degree=2, include_bias=False)))
            steps.append(("scaler", StandardScaler()))
        elif feature_mode == "lasso_selected":
            steps.append(("scaler", StandardScaler()))
        elif spec.preprocessor == "linear":
            steps.append(("scaler", StandardScaler()))

        if stage == "classification" and smote:
            steps.append(("smote", self._build_smote()))

        if feature_mode in {"lasso_selected", "poly2_lasso"}:
            steps.append(("selector", self._build_selector(stage)))

        model = spec.build_estimator()
        if stage == "regression" and multioutput:
            model = MultiOutputRegressor(model, n_jobs=1)
        steps.append(("model", model))
        if stage == "classification" and smote:
            if ImbPipeline is None or SMOTE is None:
                raise ImportError("imbalanced-learn no esta instalado. Instala `imbalanced-learn` para usar smote=True.")
            return ImbPipeline(steps)
        return SklearnPipeline(steps)

    def _prepare_param_grid(self, spec: ModelSpec, multioutput: bool = False) -> dict[str, list[Any]]:
        if not multioutput:
            return spec.param_grid
        return {
            key.replace("model__", "model__estimator__"): values
            for key, values in spec.param_grid.items()
        }

    def _build_smote(self):
        if SMOTE is None:
            raise ImportError("imbalanced-learn no esta instalado. Instala `imbalanced-learn` para usar smote=True.")
        return SMOTE(random_state=self.random_state, k_neighbors=1)

    def _build_selector(self, stage: str):
        if stage == "regression":
            return SelectFromModel(
                estimator=Lasso(alpha=0.001, max_iter=5000, random_state=self.random_state),
                threshold="median",
            )
        return SelectFromModel(
            estimator=LogisticRegression(
                penalty="l1",
                solver="saga",
                C=0.5,
                max_iter=4000,
                random_state=self.random_state,
                multi_class="auto",
            ),
            threshold="median",
        )

    def _resolve_mode_columns(self, frame: pd.DataFrame, preset_or_columns, stage: str, feature_mode: str) -> list[str]:
        base_columns = resolve_feature_columns(frame, preset_or_columns, stage=stage)
        if feature_mode == "normal":
            return base_columns
        if feature_mode == "extra":
            return available_numeric_features(frame)
        if feature_mode == "lasso_selected":
            return available_numeric_features(frame)
        if feature_mode == "poly2_lasso":
            return base_columns
        raise ValueError(f"Unsupported feature mode: {feature_mode}")

    def _scoring_config(self, stage: str):
        if stage == "regression":
            return {"r2": "r2", "neg_mae": "neg_mean_absolute_error", "neg_rmse": "neg_root_mean_squared_error"}, "r2"
        return {"accuracy": "accuracy", "f1_weighted": "f1_weighted"}, "accuracy"

    def _evaluate_regressor(self, estimator, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, float]:
        predictions = estimator.predict(X_test)
        return {
            "mae": float(mean_absolute_error(y_test, predictions)),
            "rmse": _rmse(y_test, predictions),
            "r2": float(r2_score(y_test, predictions)),
        }

    def _evaluate_multioutput_regressor(
        self,
        estimator,
        X_test: pd.DataFrame,
        y_test: pd.DataFrame,
        target_columns: list[str],
    ) -> dict[str, Any]:
        predictions = np.asarray(estimator.predict(X_test))
        y_true = y_test.to_numpy()
        per_target_r2 = {
            column: float(r2_score(y_true[:, index], predictions[:, index]))
            for index, column in enumerate(target_columns)
        }
        return {
            "mae": float(mean_absolute_error(y_true, predictions)),
            "rmse": _rmse(y_true, predictions),
            "r2": float(r2_score(y_true, predictions, multioutput="uniform_average")),
            "per_target_r2": per_target_r2,
        }

    def _evaluate_classifier(self, estimator, X_test: pd.DataFrame, y_test: pd.Series) -> dict[str, object]:
        predictions = estimator.predict(X_test)
        return {
            "accuracy": float(accuracy_score(y_test, predictions)),
            "precision_weighted": float(precision_score(y_test, predictions, average="weighted", zero_division=0)),
            "recall_weighted": float(recall_score(y_test, predictions, average="weighted", zero_division=0)),
            "f1_weighted": float(f1_score(y_test, predictions, average="weighted", zero_division=0)),
            "confusion_matrix": confusion_matrix(y_test, predictions, labels=[0, 1, 2]).tolist(),
        }

    def _artifact_extension(self, spec: ModelSpec) -> str:
        return "pt" if spec.serializer == "pt" else "joblib"

    def _save_model(self, model, path: Path, spec: ModelSpec) -> None:
        if spec.serializer == "pt":
            if torch is None:
                raise ImportError("PyTorch no esta instalado. No se puede guardar el modelo `.pt`.")
            torch.save(model, path)
            return
        joblib.dump(model, path)

    def _load_model(self, artifact_path: str | Path):
        artifact_path = Path(artifact_path)
        if artifact_path.suffix == ".joblib":
            return joblib.load(artifact_path)
        if artifact_path.suffix == ".pt":
            if torch is None:
                raise ImportError("PyTorch no esta instalado. No se puede cargar el modelo `.pt`.")
            try:
                return torch.load(artifact_path, map_location="cpu", weights_only=False)
            except TypeError:
                return torch.load(artifact_path, map_location="cpu")
        raise ValueError(f"Formato de artefacto no soportado: {artifact_path.suffix}")

    def _load_saved_bundle(self, bundle_dir: Path, summary_filename: str, artifact_key: str) -> dict[str, Any]:
        summary_path = bundle_dir / summary_filename
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        artifact_path = summary[artifact_key]["artifact_path"]
        return {
            "summary": summary,
            "model": self._load_model(artifact_path),
            "bundle_dir": bundle_dir,
        }

    def _prediction_frame(self, predictions: np.ndarray, target_columns: list[str]) -> tuple[pd.DataFrame, list[str]]:
        predictions = np.asarray(predictions)
        if predictions.ndim == 1:
            predictions = predictions.reshape(-1, 1)
        generated_feature_columns = [f"approx_{column}" for column in target_columns]
        return pd.DataFrame(predictions, columns=generated_feature_columns), generated_feature_columns

    def _resolve_advanced_stage2_columns(
        self,
        frame: pd.DataFrame,
        winner_feature_set,
        feature_mode: str,
        generated_feature_columns: list[str],
    ) -> list[str]:
        base_columns = resolve_feature_columns(frame, winner_feature_set, stage="classification")
        if feature_mode == "normal":
            return [*base_columns, *generated_feature_columns]
        if feature_mode == "extra":
            return available_numeric_features(frame)
        if feature_mode == "lasso_selected":
            return available_numeric_features(frame)
        if feature_mode == "poly2_lasso":
            return [*base_columns, *generated_feature_columns]
        raise ValueError(f"Unsupported feature mode: {feature_mode}")

    def _flatten_run_summary(self, item: dict[str, object]) -> dict[str, object]:
        return {
            "run_name": item["run_name"],
            "feature_mode": item["feature_mode"],
            "smote": item["smote"],
            "regressor_name": item["regressor"]["name"],
            "classifier_name": item["classifier"]["name"],
            "regressor_cv_score": item["regressor"]["best_cv_score"],
            "classifier_cv_score": item["classifier"]["best_cv_score"],
            "regression_train_mae": item["regression_metrics"]["train"]["mae"],
            "regression_test_mae": item["regression_metrics"]["test"]["mae"],
            "regression_train_rmse": item["regression_metrics"]["train"]["rmse"],
            "regression_test_rmse": item["regression_metrics"]["test"]["rmse"],
            "regression_train_r2": item["regression_metrics"]["train"]["r2"],
            "regression_test_r2": item["regression_metrics"]["test"]["r2"],
            "winner_train_accuracy": item["classifier_metrics"]["train"]["accuracy"],
            "winner_test_accuracy": item["classifier_metrics"]["test"]["accuracy"],
            "winner_train_f1_weighted": item["classifier_metrics"]["train"]["f1_weighted"],
            "winner_test_f1_weighted": item["classifier_metrics"]["test"]["f1_weighted"],
            "regressor_params": json.dumps(item["regressor"]["best_params"]),
            "classifier_params": json.dumps(item["classifier"]["best_params"]),
        }

    def _flatten_stage1_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_name": item["run_name"],
            "target_metric": item["target_metric"],
            "regressor_name": item["regressor"]["name"],
            "regressor_cv_score": item["regressor"]["best_cv_score"],
            "regression_train_mae": item["regression_metrics"]["train"]["mae"],
            "regression_test_mae": item["regression_metrics"]["test"]["mae"],
            "regression_train_rmse": item["regression_metrics"]["train"]["rmse"],
            "regression_test_rmse": item["regression_metrics"]["test"]["rmse"],
            "regression_train_r2": item["regression_metrics"]["train"]["r2"],
            "regression_test_r2": item["regression_metrics"]["test"]["r2"],
            "regressor_params": json.dumps(item["regressor"]["best_params"]),
        }

    def _flatten_advanced_stage2_summary(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_name": item["run_name"],
            "target_metric": item["target_metric"],
            "plan_type": item.get("plan_type", "single_metric"),
            "feature_mode": item["feature_mode"],
            "smote": item["smote"],
            "generator_run_name": item["generator_model"]["run_name"],
            "generator_name": item["generator_model"]["name"],
            "generator_cv_r2": item["generator_model"]["cv_r2"],
            "generator_test_r2": item["generator_model"]["test_r2"],
            "classifier_name": item["classifier"]["name"],
            "classifier_cv_score": item["classifier"]["best_cv_score"],
            "winner_train_accuracy": item["classifier_metrics"]["train"]["accuracy"],
            "winner_test_accuracy": item["classifier_metrics"]["test"]["accuracy"],
            "winner_train_f1_weighted": item["classifier_metrics"]["train"]["f1_weighted"],
            "winner_test_f1_weighted": item["classifier_metrics"]["test"]["f1_weighted"],
            "classifier_params": json.dumps(item["classifier"]["best_params"]),
        }

    def _advanced_stage2_slug(self, plan: dict[str, Any]) -> str:
        if plan["plan_type"] == "include_all":
            return f"include_all__{plan['classifier_name']}+{plan['feature_mode']}"
        return f"{plan['target_metric']}__{plan['generator_run_name']}__{plan['classifier_name']}+{plan['feature_mode']}"

    def _select_best_generator_per_metric(self, selected_generators: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best_by_metric: dict[str, dict[str, Any]] = {}
        for item in selected_generators:
            target_metric = item["target_metric"]
            current = best_by_metric.get(target_metric)
            if current is None or item["rank"] < current["rank"]:
                best_by_metric[target_metric] = item
        return [best_by_metric[key] for key in sorted(best_by_metric)]


def run_match_model_experiments(
    match_features: pd.DataFrame,
    regressors: list[str],
    classifiers: list[str],
    goal_feature_set: str | list[str] = "goals_default",
    winner_feature_set: str | list[str] = "winner_default",
    explicit_pairs: list[tuple[str, str]] | None = None,
    feature_modes: list[str] | None = None,
    search_iterations: int = 8,
    include_stage1_prediction: bool = True,
    smote: bool = True,
    advance_modeling: bool = False,
    stage1_feature_set: str | list[str] = "history_only",
    stage1_target_set: str | list[str] = "candidate_indices",
    stage1_top_k: int = 3,
    stage1_min_r2: float = 0.15,
    include_all: bool = False,
    session_name: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, object]:
    runner = MatchPredictorAutoML(match_features=match_features, output_dir=output_dir)
    return runner.run(
        regressors=regressors,
        classifiers=classifiers,
        goal_feature_set=goal_feature_set,
        winner_feature_set=winner_feature_set,
        explicit_pairs=explicit_pairs,
        feature_modes=feature_modes,
        search_iterations=search_iterations,
        include_stage1_prediction=include_stage1_prediction,
        smote=smote,
        advance_modeling=advance_modeling,
        stage1_feature_set=stage1_feature_set,
        stage1_target_set=stage1_target_set,
        stage1_top_k=stage1_top_k,
        stage1_min_r2=stage1_min_r2,
        include_all=include_all,
        session_name=session_name,
    )
