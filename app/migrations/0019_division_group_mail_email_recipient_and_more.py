# Generated by Django 4.1.1 on 2024-05-21 16:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0018_alter_attachment_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='division',
            name='group_mail',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='email',
            name='recipient',
            field=models.TextField(default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='manager',
            name='divisions',
            field=models.ManyToManyField(related_name='managers', to='app.division'),
        ),
    ]
