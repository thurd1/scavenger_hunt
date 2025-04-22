from django.core.management.base import BaseCommand
from django.db import connection
import datetime


class Command(BaseCommand):
    help = 'Fake migrations to bypass the duplicate photo_questions_completed column issue'

    def handle(self, *args, **options):
        # Get current time in SQLite format
        now = datetime.datetime.now().isoformat()
        
        # Mark the problematic migration as applied
        with connection.cursor() as cursor:
            # Check if the migration is already marked as applied
            cursor.execute(
                "SELECT * FROM django_migrations WHERE app='hunt' AND name='0007_teamraceprogress_photo_questions_completed'"
            )
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
                    ['hunt', '0007_teamraceprogress_photo_questions_completed', now]
                )
                self.stdout.write(
                    self.style.SUCCESS('Successfully faked 0007_teamraceprogress_photo_questions_completed migration!')
                )
            else:
                self.stdout.write(
                    self.style.WARNING('Migration 0007_teamraceprogress_photo_questions_completed already marked as applied')
                )
                
        self.stdout.write(
            self.style.SUCCESS('Migration fake complete!')
        ) 