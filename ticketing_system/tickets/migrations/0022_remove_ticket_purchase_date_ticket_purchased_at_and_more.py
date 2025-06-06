# Generated by Django 5.1.7 on 2025-05-21 03:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0021_token_created_by_alter_token_used_by'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ticket',
            name='purchase_date',
        ),
        migrations.AddField(
            model_name='ticket',
            name='purchased_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(choices=[('AVAILABLE', 'Available'), ('PURCHASED', 'Purchased'), ('USED', 'Used'), ('EXPIRED', 'Expired')], default='AVAILABLE', max_length=20),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(choices=[('PURCHASE', 'Token Purchase'), ('REDEMPTION', 'Token Redemption'), ('TICKET_PURCHASE', 'Ticket Purchase')], max_length=20),
        ),
    ]
