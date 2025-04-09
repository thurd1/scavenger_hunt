from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Fake migrations to bypass the duplicate column name issue'

    def handle(self, *args, **options):
        # Mark the problematic migration as applied
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW()) "
                "ON CONFLICT (app, name) DO NOTHING",
                ['hunt', '0004_alter_lobby_options_lobby_last_accessed_and_more']
            )
            
            # Check if we need to fake 0006 too
            cursor.execute(
                "SELECT * FROM django_migrations WHERE app='hunt' AND name='0006_merge_20250408_1838'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
                    ['hunt', '0006_merge_20250408_1838']
                )
            
            # Check if we need to fake 0007 too
            cursor.execute(
                "SELECT * FROM django_migrations WHERE app='hunt' AND name='0007_lobby_updated_at'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
                    ['hunt', '0007_lobby_updated_at']
                )
                
        self.stdout.write(
            self.style.SUCCESS('Successfully faked migrations!')
        ) 