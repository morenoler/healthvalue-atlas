"""Association models and strictly temporal forecasting benchmarks."""

import json

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import PROCESSED, REPORTS, SEED

NUMERIC = [
    "lag_treatable",
    "lag_preventable",
    "log_lag_spend_real_proxy",
    "log_lag_gdp_ppp_constant",
    "lag_age65_pct",
    "lag_oop_share",
    "lag_public_share",
    "lag_urban_pct",
    "year",
]
FEATURES = [*NUMERIC, "iso3"]
SPECS = {
    "Persistence": None,
    "Ridge 1": ("ridge", 1),
    "Ridge 10": ("ridge", 10),
    "Ridge 100": ("ridge", 100),
    "Random forest 4": ("forest", 4),
    "Random forest 10": ("forest", 10),
}


def make_model(spec):
    method, parameter = spec
    preprocessing = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                NUMERIC,
            ),
            (
                "country",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["iso3"],
            ),
        ]
    )
    estimator = (
        Ridge(alpha=parameter)
        if method == "ridge"
        else RandomForestRegressor(
            n_estimators=200,
            min_samples_leaf=parameter,
            max_features=0.8,
            random_state=SEED,
            n_jobs=1,
        )
    )
    return Pipeline([("preprocess", preprocessing), ("model", estimator)])


def predict_from_train(train, test, spec):
    baseline = test.lag_treatable.to_numpy()
    if spec is None:
        return baseline
    model = make_model(spec)
    # Learn annual change around the strong persistence baseline.
    model.fit(train[FEATURES], train.treatable - train.lag_treatable)
    return np.maximum(0, baseline + model.predict(test[FEATURES]))


def interval_radius(errors, alpha=0.10):
    errors = np.sort(np.asarray(errors))
    if len(errors) == 0:
        raise ValueError("Empty calibration set")
    rank = min(len(errors), int(np.ceil((len(errors) + 1) * (1 - alpha))))
    return float(errors[rank - 1])


def forecast(panel):
    observed = panel.dropna(subset=["treatable", "lag_treatable"]).copy()
    cv_records = []
    for year in [2016, 2017, 2018, 2019]:
        train, validation = (
            observed.loc[observed.year < year],
            observed.loc[observed.year.eq(year)],
        )
        for name, spec in SPECS.items():
            predicted = predict_from_train(train, validation, spec)
            for (_, row), value in zip(validation.iterrows(), predicted):
                cv_records.append(
                    {
                        "model": name,
                        "year": year,
                        "iso3": row.iso3,
                        "actual": row.treatable,
                        "predicted": float(value),
                        "absolute_error": abs(row.treatable - value),
                    }
                )
    cv = pd.DataFrame(cv_records)
    cv.to_csv(REPORTS / "validation_predictions.csv", index=False)
    scores = cv.groupby("model").absolute_error.mean().sort_values()
    selected = str(scores.index[0])
    train = observed.loc[observed.year <= 2019]
    calibration = observed.loc[observed.year.between(2020, 2021)]
    test = observed.loc[observed.year.between(2022, 2023)]
    results, metrics = [], []
    for name, spec in SPECS.items():
        calibration_pred = predict_from_train(train, calibration, spec)
        radius = interval_radius(
            np.abs(calibration.treatable.to_numpy() - calibration_pred)
        )
        predicted = predict_from_train(train, test, spec)
        lower, upper = np.maximum(0, predicted - radius), predicted + radius
        metrics.append(
            {
                "model": name,
                "validation_mae": float(scores[name]),
                "test_mae": float(mean_absolute_error(test.treatable, predicted)),
                "test_rmse": float(
                    np.sqrt(mean_squared_error(test.treatable, predicted))
                ),
                "interval_coverage": float(
                    np.mean((test.treatable >= lower) & (test.treatable <= upper))
                ),
                "interval_radius": radius,
                "test_n": len(test),
                "selected": name == selected,
            }
        )
        if name == selected:
            for (_, row), value, lo, hi in zip(
                test.iterrows(), predicted, lower, upper
            ):
                results.append(
                    {
                        "iso3": row.iso3,
                        "country": row.country,
                        "year": int(row.year),
                        "actual": float(row.treatable),
                        "predicted": float(value),
                        "lower": float(lo),
                        "upper": float(hi),
                        "baseline": float(row.lag_treatable),
                    }
                )
    metric_df = pd.DataFrame(metrics).sort_values("validation_mae")
    metric_df.to_csv(REPORTS / "model_metrics.csv", index=False)
    pd.DataFrame(results).to_csv(REPORTS / "test_predictions.csv", index=False)
    # Country bootstrap keeps each country's two test years together.
    predictions = pd.DataFrame(results)
    errors = predictions.assign(
        absolute_error=(predictions.actual - predictions.predicted).abs(),
        baseline_error=(predictions.actual - predictions.baseline).abs(),
    )
    errors.groupby("year").agg(
        n=("iso3", "size"),
        mae=("absolute_error", "mean"),
        baseline_mae=("baseline_error", "mean"),
    ).to_csv(REPORTS / "errors_by_year.csv")
    errors.groupby(["iso3", "country"]).agg(
        n=("year", "size"),
        mae=("absolute_error", "mean"),
        baseline_mae=("baseline_error", "mean"),
    ).sort_values("mae", ascending=False).to_csv(REPORTS / "errors_by_country.csv")
    # Explain the selected configuration on a validation year, never tune on test.
    importance_rows = []
    if SPECS[selected] is not None:
        explain_train = observed.loc[observed.year <= 2018]
        explain_validation = observed.loc[observed.year.eq(2019)]
        explain_model = make_model(SPECS[selected])
        explain_model.fit(
            explain_train[FEATURES],
            explain_train.treatable - explain_train.lag_treatable,
        )
        importance = permutation_importance(
            explain_model,
            explain_validation[FEATURES],
            explain_validation.treatable - explain_validation.lag_treatable,
            scoring="neg_mean_absolute_error",
            n_repeats=20,
            random_state=SEED,
        )
        importance_rows = sorted(
            [
                {"feature": name, "mae_increase": float(avg), "shuffle_std": float(std)}
                for name, avg, std in zip(
                    FEATURES, importance.importances_mean, importance.importances_std
                )
            ],
            key=lambda r: r["mae_increase"],
            reverse=True,
        )
    pd.DataFrame(
        importance_rows, columns=["feature", "mae_increase", "shuffle_std"]
    ).to_csv(REPORTS / "validation_importance.csv", index=False)
    improvement = (
        predictions.assign(
            gain=(predictions.actual - predictions.baseline).abs()
            - (predictions.actual - predictions.predicted).abs()
        )
        .groupby("iso3")
        .gain.agg(["sum", "count"])
    )
    rng = np.random.default_rng(SEED)
    samples = rng.integers(0, len(improvement), size=(2000, len(improvement)))
    gains = improvement["sum"].to_numpy()[samples].sum(axis=1) / improvement[
        "count"
    ].to_numpy()[samples].sum(axis=1)
    summary = {
        "selected_model": selected,
        "selection_metric": "Pooled MAE across 2016-2019 rolling validation folds",
        "train_last_year": 2019,
        "calibration_years": [2020, 2021],
        "test_years": [2022, 2023],
        "train_n": len(train),
        "calibration_n": len(calibration),
        "test_n": len(test),
        "improvement_vs_persistence_ci95": np.quantile(gains, [0.025, 0.975]).tolist(),
        "metrics": metric_df.to_dict(orient="records"),
        "validation_importance": importance_rows,
    }
    (REPORTS / "forecast.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def associations(panel):
    required = [
        "log_treatable",
        "log_lag_spend_real_proxy",
        "log_lag_gdp_ppp_constant",
        "lag_age65_pct",
        "lag_oop_share",
    ]
    frame = panel.dropna(subset=required).copy()
    trend_columns = []
    for code in sorted(frame.iso3.unique())[1:]:
        column = f"trend_{code}"
        frame[column] = (frame.iso3 == code).astype(float) * (frame.year - 2010)
        trend_columns.append(column)
    base = "log_treatable ~ log_lag_spend_real_proxy + log_lag_gdp_ppp_constant + lag_age65_pct + lag_oop_share"
    configurations = [
        ("Pooled association", frame, base + " + C(year)"),
        ("Country + year effects", frame, base + " + C(iso3) + C(year)"),
        ("Before 2020", frame.loc[frame.year < 2020], base + " + C(iso3) + C(year)"),
        (
            "High income",
            frame.loc[frame.income_group.eq("High income")],
            base + " + C(iso3) + C(year)",
        ),
        (
            "Country trends",
            frame,
            base + " + C(iso3) + C(year) + " + " + ".join(trend_columns),
        ),
    ]
    estimates = []
    main_coefficients = None
    for name, data, formula in configurations:
        design = smf.ols(formula, data=data)
        if np.linalg.matrix_rank(design.exog) < design.exog.shape[1]:
            raise ValueError(f"Rank-deficient design: {name}")
        model = design.fit(
            cov_type="cluster",
            cov_kwds={"groups": data.iso3, "use_correction": True},
            use_t=True,
        )
        term = "log_lag_spend_real_proxy"
        coefficient = float(model.params[term])
        low, high = model.conf_int().loc[term].tolist()
        estimates.append(
            {
                "specification": name,
                "coefficient": coefficient,
                "ci_low": low,
                "ci_high": high,
                "p_value": float(model.pvalues[term]),
                "n": int(model.nobs),
                "countries": data.iso3.nunique(),
                "r_squared": float(model.rsquared),
                "change_10pct": 100 * (1.1**coefficient - 1),
                "change_10pct_low": 100 * (1.1**low - 1),
                "change_10pct_high": 100 * (1.1**high - 1),
            }
        )
        if name == "Country + year effects":
            main_coefficients = [
                {
                    "term": term_name,
                    "coefficient": float(model.params[term_name]),
                    "ci_low": float(model.conf_int().loc[term_name, 0]),
                    "ci_high": float(model.conf_int().loc[term_name, 1]),
                }
                for term_name in required[1:]
            ]
    pd.DataFrame(estimates).to_csv(REPORTS / "association_estimates.csv", index=False)
    pd.DataFrame(main_coefficients).to_csv(
        REPORTS / "main_coefficients.csv", index=False
    )
    result = {
        "estimates": estimates,
        "main": estimates[1],
        "inference": "Country-clustered standard errors, t intervals",
        "causal": False,
    }
    (REPORTS / "associations.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def main():
    panel = pd.read_csv(PROCESSED / "panel.csv")
    association = associations(panel)
    prediction = forecast(panel)
    print(
        json.dumps(
            {
                "association": association["main"],
                "forecast": prediction["selected_model"],
            },
            indent=2,
        )
    )
    return association, prediction


if __name__ == "__main__":
    main()
