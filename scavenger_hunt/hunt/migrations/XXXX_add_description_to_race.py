from django.db import migrations, models

operations = [
    migrations.AddField(
        model_name='race',
        name='description',
        field=models.TextField(blank=True, default=''),
        preserve_default=False,
    ),
] 