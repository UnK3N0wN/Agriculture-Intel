import pytest

@pytest.fixture(autouse=True)
def no_normals(monkeypatch):
    monkeypatch.setattr("apps.crops.views.get_climate_normals", lambda lat, lon: None)