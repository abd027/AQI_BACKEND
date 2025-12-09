"""
Django management command to send a test AQI alert email
Useful for testing email functionality

Usage:
    python manage.py test_aqi_email --email user@example.com
    python manage.py test_aqi_email --email user@example.com --aqi 120
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from aqi.models import SavedLocation
from aqi.utils import send_aqi_alert_email

User = get_user_model()


class Command(BaseCommand):
    help = 'Send a test AQI alert email to the specified email address'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email address to send test email to',
        )
        parser.add_argument(
            '--aqi',
            type=float,
            default=120.0,
            help='AQI value to use in test email (default: 120)',
        )
        parser.add_argument(
            '--city',
            type=str,
            default='Test City',
            help='City name for test location (default: Test City)',
        )
        parser.add_argument(
            '--lat',
            type=float,
            default=40.7128,
            help='Latitude for test location (default: 40.7128 - New York)',
        )
        parser.add_argument(
            '--lon',
            type=float,
            default=-74.0060,
            help='Longitude for test location (default: -74.0060 - New York)',
        )

    def handle(self, *args, **options):
        email = options['email']
        aqi_value = options['aqi']
        city = options['city']
        lat = options['lat']
        lon = options['lon']
        
        self.stdout.write(self.style.SUCCESS(f'Sending test AQI alert email to {email}...'))
        
        try:
            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email.split('@')[0],
                    'is_active': True,
                    'is_verified': True,
                }
            )
            
            if created:
                self.stdout.write(self.style.WARNING(f'Created temporary user: {email}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Using existing user: {email}'))
            
            # Get or create saved location
            saved_location, loc_created = SavedLocation.objects.get_or_create(
                user=user,
                latitude=lat,
                longitude=lon,
                defaults={
                    'name': city,
                    'city': city,
                    'country': 'Test Country',
                }
            )
            
            if loc_created:
                self.stdout.write(self.style.SUCCESS(f'Created test location: {city}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Using existing location: {saved_location.name}'))
            
            # Prepare mock AQI data
            aqi_data = {
                'aqi': aqi_value,
                'location': {
                    'lat': lat,
                    'lon': lon,
                },
                'current': {
                    'pm2_5': 45.0,
                    'pm10': 60.0,
                    'o3': 120.0,
                },
                'dominant_pollutant': 'pm2_5',
                'health_recommendations': [
                    'Sensitive groups should reduce outdoor activities',
                    'Consider using an air purifier indoors',
                    'Keep windows closed if possible'
                ],
                'city': city,
            }
            
            # Send email
            self.stdout.write(self.style.SUCCESS(f'Sending email with AQI value: {aqi_value}...'))
            email_sent = send_aqi_alert_email(
                user=user,
                saved_location=saved_location,
                aqi_value=aqi_value,
                aqi_data=aqi_data
            )
            
            if email_sent:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Test email sent successfully!\n'
                        f'  Recipient: {email}\n'
                        f'  Location: {saved_location.name}\n'
                        f'  AQI Value: {aqi_value}\n'
                        f'  Threshold: 100 (email sent because AQI >= 100)'
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f'✗ Failed to send email. Check email configuration and logs.'
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error sending test email: {str(e)}')
            )
            raise

