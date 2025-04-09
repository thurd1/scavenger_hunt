from django.core.management.base import BaseCommand
from django.db import connection
import datetime


class Command(BaseCommand):
    help = 'Fake migrations to bypass the duplicate column name issue'

    def handle(self, *args, **options):
        # Get current time in SQLite format
        now = datetime.datetime.now().isoformat()
        
        # Mark the problematic migration as applied
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s) "
                "ON CONFLICT (app, name) DO NOTHING",
                ['hunt', '0004_alter_lobby_options_lobby_last_accessed_and_more', now]
            )
            
            # Check if we need to fake 0006 too
            cursor.execute(
                "SELECT * FROM django_migrations WHERE app='hunt' AND name='0006_merge_20250408_1838'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['hunt', '0006_merge_20250408_1838', now]
                )
            
            # Check if we need to fake 0007 too
            cursor.execute(
                "SELECT * FROM django_migrations WHERE app='hunt' AND name='0007_lobby_updated_at'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['hunt', '0007_lobby_updated_at', now]
                )
                
        self.stdout.write(
            self.style.SUCCESS('Successfully faked migrations!')
        ) 