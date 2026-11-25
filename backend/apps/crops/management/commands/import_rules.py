import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.crops.models import Crop, SeasonalRule

HEMISPHERES = {"N", "S", "ANY"}
ZONES = {"tropical", "subtropical", "arid", "temperate", "cold", "any"}


class Command(BaseCommand):
    help = "Import sowing windows from a CSV (columns: crop,hemisphere,climate_zone,season_label,sow_start_month,sow_end_month,source,notes)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--verified", action="store_true", help="Mark imported rules as already checked by a person")

    def handle(self, *args, **options):
        try:
            handle = open(options["csv_path"], newline="", encoding="utf-8-sig")
        except OSError as exc:
            raise CommandError(f"Cannot open file: {exc}")

        saved, errors = 0, []
        with handle, transaction.atomic():
            for line_no, row in enumerate(csv.DictReader(handle), start=2):
                try:
                    crop = Crop.objects.get(slug=row["crop"].strip())
                    hemisphere = row["hemisphere"].strip().upper()
                    zone = row["climate_zone"].strip().lower()
                    start, end = int(row["sow_start_month"]), int(row["sow_end_month"])
                    label = row["season_label"].strip()
                    if hemisphere not in HEMISPHERES:
                        raise ValueError(f"hemisphere must be one of {sorted(HEMISPHERES)}")
                    if zone not in ZONES:
                        raise ValueError(f"climate_zone must be one of {sorted(ZONES)}")
                    if not (1 <= start <= 12 and 1 <= end <= 12):
                        raise ValueError("months must be 1-12")
                    if not label:
                        raise ValueError("season_label is required")
                except Crop.DoesNotExist:
                    errors.append(f"line {line_no}: no crop with slug '{row.get('crop')}'")
                    continue
                except (KeyError, ValueError) as exc:
                    errors.append(f"line {line_no}: {exc}")
                    continue

                SeasonalRule.objects.update_or_create(
                    crop=crop, hemisphere=hemisphere, climate_zone=zone, season_label=label,
                    defaults={
                        "sow_start_month": start,
                        "sow_end_month": end,
                        "notes": (row.get("notes") or "").strip(),
                        "source": (row.get("source") or "manual").strip()[:60],
                        "verified": options["verified"],
                    },
                )
                saved += 1
            if options["dry_run"]:
                transaction.set_rollback(True)

        prefix = "DRY RUN: " if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"{prefix}saved {saved} rules, {len(errors)} problems."))
        for message in errors[:25]:
            self.stdout.write(f"  {message}")