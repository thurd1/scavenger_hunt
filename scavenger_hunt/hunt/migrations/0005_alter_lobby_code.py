from django.db import migrations, models

class Migration(migrations.Migration):
    # Change this line to point to your last existing migration
    # Look in the migrations folder for the highest numbered migration that exists
    # For example, if 0003_something exists, use that
    dependencies = [
        ('hunt', '0003_your_last_existing_migration'),  # Replace with your last migration name
    ]

    operations = [
        migrations.AlterField(
            model_name='lobby',
            name='code',
            field=models.CharField(blank=True, max_length=6, unique=True),
        ),
    ] 