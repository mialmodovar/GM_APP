# Generated by Django 4.1.1 on 2024-07-23 16:20

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("app", "0030_companycontact_remove_client_person_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="email",
            old_name="recipient",
            new_name="recipients",
        ),
    ]