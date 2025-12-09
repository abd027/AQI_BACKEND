import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breatheasy.settings')
django.setup()

from django.contrib.auth import get_user_model
from sensors.models import MQTTBrokerConfig

User = get_user_model()

def configure_users():
    """Configure MQTT for all users"""
    users = User.objects.all()
    print(f"Found {users.count()} users.")
    
    for user in users:
        # Create or update MQTT config
        # Using a public broker for testing: broker.hivemq.com
        defaults = {
            'host': 'broker.hivemq.com',
            'port': 1883,
            'topic': f'breatheasy/{user.id}/data',
            'is_active': True
        }
        
        config, created = MQTTBrokerConfig.objects.get_or_create(
            user=user,
            defaults=defaults
        )
        
        if not created:
            config.host = defaults['host']
            config.port = defaults['port']
            config.topic = defaults['topic']
            config.is_active = True
            config.save()
            
        print(f"[OK] Configured MQTT for {user.email}: {config.host}:{config.port}/{config.topic}")

if __name__ == '__main__':
    try:
        configure_users()
        print("\nAll users configured successfully.")
    except Exception as e:
        print(f"Error: {e}")
