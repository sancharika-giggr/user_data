# Generated by Django 2.2.28 on 2023-08-15 07:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_app', '0002_profile_u_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='u_id',
            field=models.CharField(max_length=16, null=True, unique=True),
        ),
    ]
