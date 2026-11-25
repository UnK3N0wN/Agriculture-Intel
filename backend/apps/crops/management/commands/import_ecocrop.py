import csv
import math
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.crops.models import Crop

SOURCE_NAME = "FAO EcoCrop"
SOURCE_URL = "https://gaez.fao.org/pages/ecocrop"

# Column names differ a little between copies of the database. Run the command with
# --show-columns, then edit this table if your file uses other names.
COLUMNS = {
    "scientific": ["ScientificName", "SCIENTNAME", "scientific_name"],
    "common": ["COMNAME", "CommonName", "common_name"],
    "category": ["CAT"],
    "temp_min": ["TMIN"],
    "temp_opt_min": ["TOPMN"],
    "temp_opt_max": ["TOPMX"],
    "temp_max": ["TMAX"],
    "rain_opt_min": ["ROPMN"],
    "rain_opt_max": ["ROPMX"],
    "days_min": ["GMIN"],
    "days_max": ["GMAX"],
    "texture": ["TEXT"],
}

REQUIRED = ["scientific", "temp_min", "temp_opt_min", "temp_opt_max", "temp_max", "rain_opt_min", "rain_opt_max", "days_min"]

CATEGORY_HINTS = [
    ("cereal", "cereal"), ("pulse", "pulse"), ("legume", "pulse"), ("vegetable", "vegetable"),
    ("root", "vegetable"), ("tuber", "vegetable"), ("fruit", "fruit"), ("oil", "oilseed"),
    ("fibre", "fibre"), ("fiber", "fibre"), ("spice", "spice"),
]

def pick(row, names):
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() not in ("", "NA", "nan", "NaN"):
            return str(value).strip()
    return None


def number(row, names):
    raw = pick(row, names)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def guess_category(text):
    lowered = (text or "").lower()
    for hint, category in CATEGORY_HINTS:
        if hint in lowered:
            return category
    return "other"


def water_need(annual_opt_max_mm):
    # Derived by this script, not a value from the database.
    if annual_opt_max_mm < 700:
        return "low"
    return "medium" if annual_opt_max_mm < 1500 else "high"


def unique_slug(name):
    base = slugify(name) or "crop"
    slug, n = base, 2
    while Crop.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def read_rows(path):
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            with open(path, newline="", encoding=encoding) as handle:
                reader = csv.DictReader(handle)
                return reader.fieldnames or [], list(reader)
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise CommandError(f"Cannot open the file: {exc}")
    raise CommandError("Could not read the file as UTF-8 or Latin-1.")


class Command(BaseCommand):
    help = "Import crop requirements from an EcoCrop CSV into the Crop table."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--only", help="Comma-separated scientific names, e.g. 'Oryza sativa,Zea mays'")
        parser.add_argument("--all", action="store_true", help="Import every row (thousands of plants)")
        parser.add_argument("--dry-run", action="store_true", help="Show what would happen, save nothing")
        parser.add_argument("--show-columns", action="store_true", help="Print the CSV column names and stop")
        parser.add_argument(
            "--rain-mode",
            choices=["season", "annual"],
            default="season",
            help="season: rainfall limits are totals over the growing period (default). annual: divide by 12.",
        )

    def handle(self, *args, **options):
        columns, rows = read_rows(options["csv_path"])
        if options["show_columns"]:
            self.stdout.write(f"{len(rows)} rows. Columns found:\n  " + "\n  ".join(columns))
            return

        missing = [key for key in REQUIRED if not any(name in columns for name in COLUMNS[key])]
        if missing:
            raise CommandError(
                "These needed columns were not found: " + ", ".join(missing)
                + ".\nColumns in your file:\n  " + "\n  ".join(columns)
                + "\nAdd the right names to COLUMNS at the top of import_ecocrop.py."
            )
        if not options["only"] and not options["all"]:
            raise CommandError("Choose crops with --only 'Oryza sativa,Zea mays' (or pass --all).")

        mode = options["rain_mode"]
        wanted = [w.strip().lower() for w in (options["only"] or "").split(",") if w.strip()]
        matched_tokens, seen = set(), set()
        created, updated, skipped = [], [], []

        with transaction.atomic():
            for row in rows:
                scientific = pick(row, COLUMNS["scientific"])
                if not scientific:
                    continue
                base = " ".join(scientific.split()[:2])
                if wanted:
                    hits = [w for w in wanted if scientific.lower().startswith(w)]
                    if not hits:
                        continue
                    matched_tokens.update(hits)
                if base.lower() in seen:
                    skipped.append(f"{base}: duplicate row (kept the first one)")
                    continue

                temps = [number(row, COLUMNS[k]) for k in ("temp_min", "temp_opt_min", "temp_opt_max", "temp_max")]
                if None in temps or not (temps[0] <= temps[1] <= temps[2] <= temps[3]):
                    skipped.append(f"{base}: temperature values missing or out of order")
                    continue
                rain_lo, rain_hi = number(row, COLUMNS["rain_opt_min"]), number(row, COLUMNS["rain_opt_max"])
                if rain_lo is None or rain_hi is None or rain_lo > rain_hi:
                    skipped.append(f"{base}: rainfall optimum missing or out of order")
                    continue
                days_min = number(row, COLUMNS["days_min"])
                if days_min is None or days_min <= 0:
                    skipped.append(f"{base}: growing-cycle length missing")
                    continue
                days_max = max(number(row, COLUMNS["days_max"]) or days_min, days_min)

                existing = Crop.objects.filter(scientific_name__iexact=base).first()
                if existing and (existing.verified or existing.source not in ("demo", SOURCE_NAME)):
                    skipped.append(f"{base}: protected (verified, or entered by a person)")
                    continue
                seen.add(base.lower())

                # Convert rainfall limits to "mm per month", matching how scoring compares them.
                cycle_months = max(1, min(12, math.ceil(days_min / 30)))
                divisor = cycle_months if mode == "season" else 12
                rain_min_month, rain_max_month = rain_lo / divisor, rain_hi / divisor

                common_raw = pick(row, COLUMNS["common"]) or ""
                common = re.split(r"[;,]", common_raw)[0].strip().title() if common_raw else ""
                texture = pick(row, COLUMNS["texture"]) or ""
                values = {
                    "scientific_name": base,
                    "category": guess_category(pick(row, COLUMNS["category"])),
                    "water_need": water_need(rain_max_month),
                    "growing_days_min": int(days_min),
                    "growing_days_max": int(days_max),
                    "temp_min_c": temps[0],
                    "temp_opt_min_c": temps[1],
                    "temp_opt_max_c": temps[2],
                    "temp_max_c": temps[3],
                    "rain_min_mm": round(rain_min_month, 1),
                    "rain_max_mm": round(rain_max_month, 1),
                    "soil_types": [t.strip().lower() for t in re.split(r"[;,/]", texture) if t.strip()],
                    "description": f"Also known as: {common_raw}" if common_raw else "",
                    "source": SOURCE_NAME,
                    "source_url": SOURCE_URL,
                    "notes": f"Imported from FAO EcoCrop. Rainfall limits converted with rain-mode '{mode}'.",
                    "verified": False,
                    "is_active": True,
                }
                if existing:
                    for key, value in values.items():
                        setattr(existing, key, value)
                    existing.save()
                    updated.append(existing.name)
                else:
                    name = common or base
                    if Crop.objects.filter(name=name).exists():
                        name = f"{name} ({base})"
                    Crop.objects.create(name=name, slug=unique_slug(name), **values)
                    created.append(name)

            if options["dry_run"]:
                transaction.set_rollback(True)

        prefix = "DRY RUN: " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}created {len(created)}, updated {len(updated)}, skipped {len(skipped)} (rain mode: {mode})."
        ))
        if created:
            self.stdout.write("  created: " + ", ".join(created[:40]))
        if updated:
            self.stdout.write("  updated: " + ", ".join(updated[:40]))
        for line in skipped[:25]:
            self.stdout.write(f"  skipped - {line}")
        unmatched = [w for w in wanted if w not in matched_tokens]
        if unmatched:
            self.stdout.write(self.style.WARNING(
                "No rows matched: " + ", ".join(unmatched) + " (the database may use an older scientific name)"
            ))