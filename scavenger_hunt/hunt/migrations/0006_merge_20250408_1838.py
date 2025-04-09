# Generated manually as a fix for missing migration

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('hunt', '0001_initial'),
        ('hunt', '0002_add_team_progress'),
        ('hunt', '0003_add_name_to_teammember'),
        ('hunt', '0004_alter_lobby_options_lobby_last_accessed_and_more'),
    ]

    operations = [
        # This is a merge migration, so no operations are needed
    ] 