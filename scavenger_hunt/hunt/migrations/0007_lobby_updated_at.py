# Generated manually as a fix for missing columns

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('hunt', '0006_merge_20250408_1838'),
    ]

    operations = [
        migrations.AddField(
            model_name='lobby',
            name='updated_at',
            field=models.DateTimeField(blank=True, null=True, default=None),
        ),
        migrations.AddField(
            model_name='lobby',
            name='last_accessed',
            field=models.DateTimeField(blank=True, null=True, default=None),
        ),
    ] 