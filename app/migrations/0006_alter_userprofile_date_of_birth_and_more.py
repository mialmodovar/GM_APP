# Generated by Django 4.1.1 on 2023-05-14 11:59

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_remove_userprofile_request_counter_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='date_of_birth',
            field=models.DateField(default=datetime.datetime(2000, 1, 1, 0, 0)),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='gender',
            field=models.CharField(choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], default='Other', max_length=10),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='height',
            field=models.FloatField(default=175.0),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='weight',
            field=models.FloatField(default=70.0),
        ),
    ]