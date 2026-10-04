import pytest
from fastapi.testclient import TestClient

from healthvalue.api import app

client = TestClient(app)


def test_health_and_country_count():
    assert client.get("/api/health").json() == {"status": "ok", "countries": 46}
    assert len(client.get("/api/countries").json()) == 46


def test_country_and_year_filter():
    response = client.get("/api/panel?year=2023&iso3=pol")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["iso3"] == "POL"
    assert response.json()[0]["year"] == 2023
    assert client.get("/api/panel?iso3=ZZZ").status_code == 404
    assert client.get("/api/panel?year=2099").status_code == 422


@pytest.mark.parametrize("change", [-20, 0, 20])
def test_scenario_interval_direction(change):
    data = client.get(f"/api/scenario?change_pct={change}").json()
    assert data["ci95_low"] <= data["mortality_change_pct"] <= data["ci95_high"]
    assert data["causal"] is False
    if change == 0:
        assert data["mortality_change_pct"] == 0
    assert client.get("/api/scenario?change_pct=21").status_code == 422


def test_portable_dashboard_and_download():
    assert client.get("/").status_code == 200
    assert client.get("/data/atlas.json").status_code == 200
    assert client.get("/data/world.json").status_code == 200
    response = client.get("/data/panel.csv")
    assert response.status_code == 200
    assert response.text.startswith("iso3,year")
    assert client.get("/docs").status_code == 200
