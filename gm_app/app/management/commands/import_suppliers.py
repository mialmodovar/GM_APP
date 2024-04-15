import csv
from django.core.management.base import BaseCommand, CommandError
from app.models import Supplier

class Command(BaseCommand):
    help = 'Imports suppliers from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The CSV file path')

    def handle(self, *args, **options):
        file_path = options['csv_file']
        encodings = ['utf-8', 'ISO-8859-1']  # List of encodings to try
        for encoding in encodings:
            try:
                with open(file_path, newline='', encoding=encoding) as csvfile:
                    reader = csv.DictReader(csvfile)
                    suppliers_created = 0
                    for row in reader:
                        Supplier.objects.create(
                            name=row['name'],
                            country=row['country'],
                            contact_person=row['contact_person'],
                            email=row['email']
                        )
                        suppliers_created += 1
                self.stdout.write(self.style.SUCCESS(f'Successfully imported {suppliers_created} suppliers'))
                break  # Exit the loop if successful
            except UnicodeDecodeError as e:
                self.stdout.write(self.style.WARNING(f'Unicode decode error with {encoding}: {e}. Trying next encoding...'))
            except Exception as e:
                raise CommandError(f'Error importing suppliers with {encoding}: {e}')

        else:  # If no break occurs
            raise CommandError('Failed to import suppliers with any of the tried encodings.')
