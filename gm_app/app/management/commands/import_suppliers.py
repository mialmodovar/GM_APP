import csv
from django.core.management.base import BaseCommand, CommandError
from app.models import Supplier, Product, Division

class Command(BaseCommand):
    help = 'Imports suppliers from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The CSV file path')

    def handle(self, *args, **options):
        file_path = options['csv_file']
        encodings = ['utf-8', 'ISO-8859-1']  # List of encodings to try
        required_fields = ['name', 'country', 'contact_person', 'email', 'products', 'division']

        for encoding in encodings:
            try:
                with open(file_path, newline='', encoding=encoding) as csvfile:
                    reader = csv.DictReader(csvfile)
                    
                    # Check if all required fields are in the CSV
                    if not all(field in reader.fieldnames for field in required_fields):
                        raise CommandError('CSV file is missing one or more required fields.')

                    suppliers_created = 0
                    for row in reader:
                        products = row.get('products', '').split(',')  # Assuming products are comma-separated in the CSV
                        division_name = row.get('division', '')

                        # Get or create the division
                        division, _ = Division.objects.get_or_create(name=division_name)

                        # Create or update the supplier
                        supplier, created = Supplier.objects.update_or_create(
                            name=row['name'],
                            defaults={
                                'country': row['country'],
                                'contact_person': row['contact_person'],
                                'email': row['email'],
                                'division': division,
                            }
                        )

                        # Clear existing product relationships and add new ones
                        supplier.products.clear()
                        for product_name in products:
                            if product_name:  # Ensure the product name is not empty
                                product, _ = Product.objects.get_or_create(name=product_name.strip())
                                supplier.products.add(product)

                        suppliers_created += 1

                self.stdout.write(self.style.SUCCESS(f'Successfully imported {suppliers_created} suppliers'))
                break  # Exit the loop if successful
            except UnicodeDecodeError as e:
                self.stdout.write(self.style.WARNING(f'Unicode decode error with {encoding}: {e}. Trying next encoding...'))
            except KeyError as e:
                raise CommandError(f'Missing expected field in CSV: {e}')
            except Exception as e:
                raise CommandError(f'Error importing suppliers with {encoding}: {e}')

        else:  # If no break occurs
            raise CommandError('Failed to import suppliers with any of the tried encodings.')