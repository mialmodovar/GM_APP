# Generated by Django 4.1.1 on 2024-05-17 16:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0017_division_remove_request_customer_feedback_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='file',
            field=models.FileField(upload_to='email_attachments/%Y/%m/%d/'),
        ),
    ]