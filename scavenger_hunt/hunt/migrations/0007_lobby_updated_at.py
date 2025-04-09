# Generated manually as a fix for missing columns
# This migration was originally intended to add updated_at to Lobby,
# but that field has already been added in migration 0004.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hunt', '0006_merge_20250408_1838'),
    ]

    operations = [
        # No operations needed - updated_at field was already added in migration 0004
    ] 