# Generated by Django 5.1.7 on 2025-05-14 03:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0012_alter_ticket_unique_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='unique_code',
            field=models.CharField(db_index=True, default='19EFEDE5E8B14AB48', max_length=17, unique=True),
        ),
    ]
