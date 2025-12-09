import os
import django
import sys
import json
import time
import paho.mqtt.client as mqtt

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breatheasy.settings')
django.setup()

from django.contrib.auth import get_user_model
from sensors.models import MQTTBrokerConfig, SensorReading

User = get_user_model()

def test_sensor_flow():
    # Get the user and config
    user = User.objects.first()
    if not user:
        print("No user found!")
        return

    config = MQTTBrokerConfig.objects.get(user=user)
    print(f"Testing for user: {user.email}")
    print(f"Target Broker: {config.host}:{config.port}")
    print(f"Target Topic: {config.topic}")

    # Create test payload
    payload = {
        "temp_c": 28.5,
        "humidity": 45.0,
        "mq7_co": 3.5,
        "mq135_co2": 420.0,
        "mq4_ch4": 1.5,
        "timestamp": time.time()  # unique marker
    }
    
    # Publish data
    print("\nPublishing message...")
    client = mqtt.Client(client_id="test_publisher")
    
    try:
        client.connect(config.host, config.port, 60)
        client.publish(config.topic, json.dumps(payload))
        client.disconnect()
        print("[OK] Message published successfully")
    except Exception as e:
        print(f"[ERROR] Failed to publish: {e}")
        return

    # Wait for listener to process
    print("\nWaiting 5 seconds for listener to process...")
    time.sleep(5)

    # Unique timestamp for this test run
    test_timestamp = payload['timestamp']
    print(f"Test Timestamp: {test_timestamp}")

    # Check database
    try:
        # Give it a few attempts
        found = False
        for i in range(3):
            try:
                # Look for reading with our specific data
                # We query by user and order by received_at, then check the JSON data
                reading = SensorReading.objects.filter(user=user).latest('received_at')
                
                stored_data = reading.data or {}
                stored_ts = stored_data.get('timestamp')
                
                print(f"Latest Reading Timestamp in DB: {stored_ts}")
                
                 # Check if this is our message (allow small float diff or exact match)
                if stored_ts == test_timestamp:
                    print(f"\n[SUCCESS] VERIFICATION SUCCESS: Data received and stored correctly!")
                    print(f"Temp: {reading.temperature}, AQI: {reading.calculated_aqi}")
                    found = True
                    break
                else:
                    print(f"Found old/different data. Retrying in 2s... ({i+1}/3)")
                    time.sleep(2)
            except SensorReading.DoesNotExist:
                print("No readings found. Retrying...")
                time.sleep(2)
        
        if not found:
            print("\n[FAILED] VERIFICATION FAILED: Could not find the specific test message in DB.")
            
    except Exception as e:
        print(f"\n[ERROR] Verification error: {e}")

if __name__ == '__main__':
    test_sensor_flow()
