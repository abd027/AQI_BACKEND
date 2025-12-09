"""
Django management command to manually trigger AQI alert check
Useful for testing and as backup if Celery is unavailable

Usage:
    python manage.py check_aqi_alerts
"""
from django.core.management.base import BaseCommand
from aqi.tasks import check_and_send_aqi_alerts


class Command(BaseCommand):
    help = 'Manually check AQI for all saved locations and send email alerts if threshold exceeded'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually sending emails (for testing)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting AQI alert check...'))
        
        if options['dry_run']:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No emails will be sent'))
        
        try:
            # Call the task function directly (not as a Celery task)
            result = check_and_send_aqi_alerts()
            
            if result['status'] == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Check completed successfully\n"
                        f"  Notifications sent: {result.get('notifications_sent', 0)}\n"
                        f"  Locations checked: {result.get('locations_checked', 0)}\n"
                        f"  Users checked: {result.get('users_checked', 0)}"
                    )
                )
                
                if result.get('errors'):
                    self.stdout.write(
                        self.style.WARNING(
                            f"\n⚠ {result.get('error_count', 0)} errors occurred:"
                        )
                    )
                    for error in result.get('errors', [])[:10]:  # Show first 10 errors
                        self.stdout.write(self.style.ERROR(f"  - {error}"))
                    if len(result.get('errors', [])) > 10:
                        self.stdout.write(
                            self.style.WARNING(
                                f"  ... and {len(result.get('errors', [])) - 10} more errors"
                            )
                        )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Check failed: {result.get('message', 'Unknown error')}"
                    )
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error running AQI alert check: {str(e)}')
            )
            raise

