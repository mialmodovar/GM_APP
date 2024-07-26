# Generated by Django 5.0.6 on 2024-05-15 13:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0013_userprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='access_token',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='expiry_token',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='refresh_token',
            field=models.TextField(blank=True, null=True),
        ),
    ]