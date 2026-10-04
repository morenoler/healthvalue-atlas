import json

import numpy as np
import pandas as pd
import pytest

from healthvalue import models
from healthvalue.config import PROCESSED, WEB
from healthvalue.prepare import add_lags, validate_panel, verify_snapshot


def test_source_checksums_and_panel_keys():
    assert len(verify_snapshot()) == 11
    panel = pd.read_csv(PROCESSED / "panel.csv")
    validate_panel(panel)
    assert len(panel) == 46 * 14
    assert panel.treatable.isna().sum() == 30


def test_lags_do_not_cross_country_or_calendar_gap():
    cols = [
        "treatable",
        "preventable",
        "spend_real_proxy",
        "gdp_ppp_constant",
        "age65_pct",
        "oop_share",
        "public_share",
        "urban_pct",
    ]
    frame = pd.DataFrame(
        {
            "iso3": ["AAA", "AAA", "AAA", "BBB"],
            "year": [2010, 2011, 2013, 2011],
            **{c: [10.0, 20.0, 30.0, 90.0] for c in cols},
        }
    )
    lagged = add_lags(frame)
    assert lagged.loc[1, "lag_treatable"] == 10
    assert lagged.loc[[0, 2, 3], "lag_treatable"].isna().all()


def test_duplicate_keys_rejected():
    panel = pd.read_csv(PROCESSED / "panel.csv")
    with pytest.raises(ValueError, match="Duplicate"):
        validate_panel(pd.concat([panel, panel.iloc[[0]]]))


def test_invalid_percent_rejected():
    panel = pd.read_csv(PROCESSED / "panel.csv")
    panel.loc[0, "oop_share"] = 101
    with pytest.raises(ValueError, match="Out-of-range"):
        validate_panel(panel)


def test_preprocessing_fits_training_statistics_only():
    train = pd.DataFrame({c: [1.0, 2.0, np.nan, 4.0] for c in models.NUMERIC})
    train["iso3"] = ["AAA", "BBB", "AAA", "BBB"]
    model = models.make_model(("ridge", 10))
    model.fit(train[models.FEATURES], [1.0, 2.0, 3.0, 4.0])
    numeric = model.named_steps["preprocess"].named_transformers_["numeric"]
    before = numeric.named_steps["imputer"].statistics_.copy()
    future = pd.DataFrame({c: [1e6] for c in models.NUMERIC})
    future["iso3"] = "NEW"
    assert np.isfinite(model.predict(future)).all()
    np.testing.assert_array_equal(before, numeric.named_steps["imputer"].statistics_)
    np.testing.assert_array_equal(before, np.full(len(models.NUMERIC), 2.0))


def test_forecast_split_and_selection_do_not_use_test(monkeypatch, tmp_path):
    calls = []

    def fake_predict(train, test, spec):
        calls.append((int(train.year.max()), set(test.year)))
        assert train.year.max() < test.year.min()
        return test.lag_treatable.to_numpy() + (0 if spec is None else 100)

    monkeypatch.setattr(models, "predict_from_train", fake_predict)
    monkeypatch.setattr(
        models, "SPECS", {"Persistence": None, "Ridge 10": ("ridge", 10)}
    )
    monkeypatch.setattr(models, "REPORTS", tmp_path)
    panel = pd.read_csv(PROCESSED / "panel.csv")
    summary = models.forecast(panel)
    cv_before = pd.read_csv(tmp_path / "validation_predictions.csv")
    panel.loc[panel.year >= 2020, "treatable"] += 1000
    changed = models.forecast(panel)
    pd.testing.assert_frame_equal(
        cv_before, pd.read_csv(tmp_path / "validation_predictions.csv")
    )
    assert summary["selected_model"] == changed["selected_model"]
    assert any(train == 2019 and years == {2020, 2021} for train, years in calls)
    assert any(train == 2019 and years == {2022, 2023} for train, years in calls)


def test_calibration_quantile_uses_finite_sample_rank():
    assert models.interval_radius(np.arange(1, 11), alpha=0.1) == 10
    with pytest.raises(ValueError, match="Empty"):
        models.interval_radius([])


def test_dashboard_snapshot_matches_panel_and_metrics():
    data = json.loads((WEB / "data" / "atlas.json").read_text(encoding="utf-8"))
    panel = pd.read_csv(PROCESSED / "panel.csv")
    assert len(data["panel"]) == len(panel)
    assert sum(r["treatable"] is None for r in data["panel"]) == 30
    assert sum(m["selected"] for m in data["forecast"]["metrics"]) == 1
    predictions = pd.DataFrame(data["predictions"])
    chosen = next(m for m in data["forecast"]["metrics"] if m["selected"])
    assert np.mean(np.abs(predictions.actual - predictions.predicted)) == pytest.approx(
        chosen["test_mae"], abs=1e-5
    )
    assert (predictions.lower <= predictions.predicted).all()
    assert (predictions.predicted <= predictions.upper).all()
