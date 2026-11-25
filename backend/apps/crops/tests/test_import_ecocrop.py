import csv
from io import StringIO

import pytest
from django.core.management import call_command

from apps.crops.models import Crop
from apps.crops.tests.test_services import make_crop

pytestmark = pytest.mark.django_db

HEADER = ["ScientificName", "COMNAME", "CAT", "TMIN", "TOPMN", "TOPMX", "TMAX",
          "ROPMN", "ROPMX", "RMIN", "RMAX", "GMIN", "GMAX", "TEXT"]
RICE = ["Oryza sativa L.", "Rice, paddy rice", "cereals", 10, 21, 28, 34, 1500, 2000, 1000, 3000, 110, 180, "heavy, medium"]
MAIZE = ["Zea mays", "Maize", "cereals", 10, 18, 27, 35, 600, 1200, 400, 1800, 80, 140, "medium"]
BROKEN = ["Bad crop", "Bad", "other", "", "", "", "", 100, 200, 50, 300, 90, 120, ""]
WHEAT = ["Triticum aestivum", "Wheat", "cereals", 3, 12, 25, 30, 400, 800, 250, 1000, 110, 150, "medium"]


def write_csv(tmp_path, *rows):
    path = tmp_path / "ecocrop.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)
    return str(path)


def run(path, *args):
    out = StringIO()
    call_command("import_ecocrop", path, *args, stdout=out)
    return out.getvalue()


def test_imports_rice_with_season_rainfall(tmp_path):
    path = write_csv(tmp_path, RICE, RICE, MAIZE, BROKEN)
    output = run(path, "--only", "Oryza sativa,Zea mays,Bad crop")

    rice = Crop.objects.get(scientific_name="Oryza sativa")
    assert rice.name == "Rice" and rice.source == "FAO EcoCrop" and rice.verified is False
    assert (rice.temp_min_c, rice.temp_opt_min_c, rice.temp_opt_max_c, rice.temp_max_c) == (10, 21, 28, 34)
    assert rice.growing_days_min == 110 and rice.growing_days_max == 180
    assert (rice.rain_min_mm, rice.rain_max_mm) == (375.0, 500.0)  # 110 days -> 4 months: 1500/4, 2000/4
    assert rice.soil_types == ["heavy", "medium"]

    maize = Crop.objects.get(scientific_name="Zea mays")
    assert (maize.rain_min_mm, maize.rain_max_mm) == (200.0, 400.0)  # 80 days -> 3 months
    assert not Crop.objects.filter(scientific_name="Bad crop").exists()
    assert "duplicate" in output and "temperature values missing" in output


def test_annual_rain_mode_divides_by_twelve(tmp_path):
    run(write_csv(tmp_path, RICE), "--only", "Oryza sativa", "--rain-mode", "annual")
    rice = Crop.objects.get(scientific_name="Oryza sativa")
    assert (rice.rain_min_mm, rice.rain_max_mm) == (125.0, 166.7)


def test_dry_run_saves_nothing(tmp_path):
    output = run(write_csv(tmp_path, RICE), "--only", "Oryza sativa", "--dry-run")
    assert "DRY RUN" in output and Crop.objects.count() == 0


def test_demo_crop_is_upgraded_in_place(tmp_path):
    demo = make_crop("Rice", rules=(), scientific_name="Oryza sativa")
    run(write_csv(tmp_path, RICE), "--only", "Oryza sativa")
    demo.refresh_from_db()
    assert Crop.objects.count() == 1
    assert demo.source == "FAO EcoCrop" and demo.temp_opt_min_c == 21


def test_verified_crop_is_never_overwritten(tmp_path):
    keep = make_crop("Wheat", rules=(), scientific_name="Triticum aestivum", verified=True, source="manual")
    output = run(write_csv(tmp_path, WHEAT), "--only", "Triticum aestivum")
    keep.refresh_from_db()
    assert keep.temp_min_c == 18 and keep.source == "manual"  # unchanged
    assert "protected" in output


def test_missing_column_gives_a_helpful_error(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Foo,Bar\n1,2\n", encoding="utf-8")
    with pytest.raises(Exception) as exc:
        run(str(path), "--only", "x")
    assert "Columns in your file" in str(exc.value)