import csv
from django.core.management.base import BaseCommand, CommandError
from app.models import Supplier, Product, Division, CompanyContact


class Command(BaseCommand):
    help = 'Imports suppliers from a CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='The CSV file path')

    def handle(self, *args, **options):
        file_path = options['csv_file']
        encodings = ['utf-8', 'ISO-8859-1']  # List of encodings to try
        required_fields = ['name', 'country',
                           'contact_person', 'email', 'products', 'division']

        for encoding in encodings:
            try:
                with open(file_path, newline='', encoding=encoding) as csvfile:
                    reader = csv.DictReader(csvfile)

                    # Check if all required fields are in the CSV
                    if not all(field in reader.fieldnames for field in required_fields):
                        raise CommandError(
                            'CSV file is missing one or more required fields.')

                    suppliers_created = 0
                    for row in reader:
                        # Assuming products are comma-separated in the CSV
                        products = row.get('products', '').split(',')
                        division_name = row.get('division', '')

                        # Get or create the division
                        division, _ = Division.objects.get_or_create(
                            name=division_name)

                        # Handle contact persons and emails
                        contact_names = row.get(
                            'contact_person', '').split(';')
                        emails = row.get('email', '').split(';')

                        # Ensure no duplicate empty fields
                        contact_names = [name.strip() for name in contact_names if name.strip()]
                        emails = [email.strip() for email in emails if email.strip()]

                        contact_persons = []
                        for i in range(max(len(contact_names), len(emails))):
                            contact_name = contact_names[i] if i < len(contact_names) else ''
                            email = emails[i] if i < len(emails) else ''

                            if contact_name or email:  # Ensure at least one of the fields is not empty
                                contact_person, _ = CompanyContact.objects.get_or_create(
                                    name=contact_name,
                                    defaults={'email': email}
                                )
                                # Update email if contact name exists but email was missing
                                if contact_name and not contact_person.email:
                                    contact_person.email = email
                                    contact_person.save()
                                contact_persons.append(contact_person)

                        # Create or update the supplier
                        supplier, created = Supplier.objects.update_or_create(
                            name=row['name'],
                            defaults={
                                'country': row['country'],
                                'division': division,
                            }
                        )

                        # Clear existing product relationships and add new ones
                        supplier.products.clear()
                        for product_name in products:
                            if product_name:  # Ensure the product name is not empty
                                product, _ = Product.objects.get_or_create(
                                    name=product_name.strip())
                                supplier.products.add(product)

                        # Clear existing contact relationships and add new ones
                        supplier.contacts.clear()
                        for contact_person in contact_persons:
                            supplier.contacts.add(contact_person)

                        suppliers_created += 1

                self.stdout.write(self.style.SUCCESS(
                    f'Successfully imported {suppliers_created} suppliers'))
                break  # Exit the loop if successful
            except UnicodeDecodeError as e:
                self.stdout.write(self.style.WARNING(
                    f'Unicode decode error with {encoding}: {e}. Trying next encoding...'))
            except KeyError as e:
                raise CommandError(f'Missing expected field in CSV: {e}')
            except Exception as e:
                raise CommandError(
                    f'Error importing suppliers with {encoding}: {e}')

        else:  # If no break occurs
            raise CommandError(
                'Failed to import suppliers with any of the tried encodings.')
