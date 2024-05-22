# Generated by Django 4.1.1 on 2024-05-21 18:48

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0019_division_group_mail_email_recipient_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='email',
            name='status',
            field=models.CharField(choices=[('SENT', 'Sent'), ('FAILED', 'Failed'), ('DRAFT', 'Draft')], default='DRAFT', max_length=10),
        ),
    ]
