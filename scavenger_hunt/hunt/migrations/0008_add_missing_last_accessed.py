# Generated manually to add missing column

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hunt', '0007_lobby_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='lobby',
            name='last_accessed',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ] 