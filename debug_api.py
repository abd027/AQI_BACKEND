
import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breatheasy.settings')
django.setup()

from aqi.services import OpenMeteoAQIService

service = OpenMeteoAQIService()
# Use coordinates for New York
data = service.fetch_hourly_aqi(40.7128, -74.0060, hours=168)

if data and 'hourly' in data:
    times = data['hourly'].get('time', [])
    print(f"Requested 168 hours. Received {len(times)} hours.")
    print(f"Start: {times[0] if times else 'None'}")
    print(f"End: {times[-1] if times else 'None'}")
else:
    print("No data received")
