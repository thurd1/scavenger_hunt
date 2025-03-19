from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('hunt', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='race',
            name='start_location',
            field=models.CharField(default='Default Location', max_length=200),
        ),
        migrations.AddField(
            model_name='race',
            name='time_limit_minutes',
            field=models.IntegerField(default=60),
        ),
    ] 