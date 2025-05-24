# tickets/migrations/0010_add_unique_constraint.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('tickets', '0009_generate_unique_code'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='unique_code',
            field=models.CharField(max_length=17, unique=True),
        ),
    ]