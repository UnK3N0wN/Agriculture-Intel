from django.core.management.base import BaseCommand

from apps.crops.services.climate import get_climate_normals

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class Command(BaseCommand):
    help = "Print the long-term monthly climate for a place. Example: python manage.py show_climate 12.97 77.59"

    def add_arguments(self, parser):
        parser.add_argument("latitude", type=float)
        parser.add_argument("longitude", type=float)

    def handle(self, *args, **options):
        normals = get_climate_normals(options["latitude"], options["longitude"])
        if normals is None:
            self.stderr.write("Could not get climate data (no internet, or the weather service refused). Check the server log.")
            return
        cell = normals["cell"]
        self.stdout.write(f"Source: {normals['source']} | {normals['years']} years | grid cell {cell['lat']}, {cell['lon']}")
        self.stdout.write("Month   Temp C   Rain mm")
        for i, name in enumerate(MONTHS):
            self.stdout.write(f"{name:<6} {normals['temp_c'][i]:>7.1f} {normals['rain_mm'][i]:>9.1f}")
        self.stdout.write(f"Total rain per year: {sum(normals['rain_mm']):.0f} mm")