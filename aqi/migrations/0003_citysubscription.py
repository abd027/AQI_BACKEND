# Generated migration for CitySubscription model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('aqi', '0002_aqinotification'),
    ]

    operations = [
        migrations.CreateModel(
            name='CitySubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('city', models.CharField(max_length=200)),
                ('country', models.CharField(max_length=200)),
                ('latitude', models.FloatField()),
                ('longitude', models.FloatField()),
                ('is_active', models.BooleanField(default=True, help_text='Whether to send email notifications for this city')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='city_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'city_subscriptions',
                'ordering': ['-created_at'],
                'unique_together': {('user', 'city', 'country')},
            },
        ),
        migrations.AddIndex(
            model_name='citysubscription',
            index=models.Index(fields=['user', 'is_active'], name='city_subscr_user_id_idx'),
        ),
        migrations.AddIndex(
            model_name='citysubscription',
            index=models.Index(fields=['is_active'], name='city_subscr_is_acti_idx'),
        ),
    ]


