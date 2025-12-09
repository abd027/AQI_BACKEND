"""
Django management command to listen for MQTT sensor data

Usage:
    python manage.py mqtt_listener

This command:
- Connects to MQTT brokers for all active user configurations
- Subscribes to each user's configured topic
- Receives sensor data, calculates AQI, and stores in database
- Handles reconnections and dynamic configuration updates
"""
import json
import logging
import time
import threading
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
import paho.mqtt.client as mqtt
from sensors.models import MQTTBrokerConfig, SensorReading
from core.utils import calculate_indoor_aqi, get_aqi_category

logger = logging.getLogger(__name__)


class MQTTClientWrapper:
    """Wrapper for MQTT client with user association"""
    
    def __init__(self, config, command_instance):
        self.config = config
        self.command = command_instance
        self.client = None
        self.connected = False
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        
    def create_client(self):
        """Create and configure MQTT client"""
        client_id = self.config.client_id or f"sensor_listener_{self.config.user.id}"
        self.client = mqtt.Client(client_id=client_id)
        
        # Set username and password if provided
        if self.config.username:
            self.client.username_pw_set(self.config.username, self.config.password)
        
        # Set callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_connect_fail = self.on_connect_fail
        
        return self.client
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            self.reconnect_delay = 5  # Reset delay on successful connection
            logger.info(f"Connected to MQTT broker for user {self.config.user.email}: {self.config.host}:{self.config.port}")
            self.command.stdout.write(
                self.command.style.SUCCESS(
                    f"[OK] Connected to {self.config.host}:{self.config.port} for user {self.config.user.email}"
                )
            )
            # Subscribe to topic
            client.subscribe(self.config.topic, qos=1)
            logger.info(f"Subscribed to topic: {self.config.topic}")
        else:
            self.connected = False
            error_msg = f"Failed to connect to MQTT broker for user {self.config.user.email}: Return code {rc}"
            logger.error(error_msg)
            self.command.stdout.write(
                self.command.style.ERROR(f"[ERROR] {error_msg}")
            )
    
    def on_message(self, client, userdata, msg):
        """Callback when message is received"""
        try:
            # Parse JSON payload
            payload = msg.payload.decode('utf-8')
            data = json.loads(payload)
            
            logger.debug(f"Received message from {self.config.user.email} on topic {msg.topic}: {payload[:100]}")
            
            # Process sensor data
            self.process_sensor_data(data)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from user {self.config.user.email}: {str(e)}")
            self.command.stdout.write(
                self.command.style.ERROR(f"[ERROR] Invalid JSON from {self.config.user.email}: {str(e)}")
            )
        except Exception as e:
            logger.error(f"Error processing message from user {self.config.user.email}: {str(e)}", exc_info=True)
            self.command.stdout.write(
                self.command.style.ERROR(f"[ERROR] Error processing message from {self.config.user.email}: {str(e)}")
            )
    
    def process_sensor_data(self, data):
        """Process sensor data and save to database"""
        try:
            # Extract sensor values
            temperature = data.get('temp_c')
            humidity = data.get('humidity')
            co_ppm = data.get('mq7_co')
            co2_ppm = data.get('mq135_co2')
            ch4_ppm = data.get('mq4_ch4')
            
            
            # Calculate indoor AQI from all available sensor readings
            aqi_result = calculate_indoor_aqi(
                co_ppm=co_ppm,
                co2_ppm=co2_ppm,
                ch4_ppm=ch4_ppm
            )
            
            calculated_aqi = aqi_result.get('aqi')
            aqi_category = aqi_result.get('category')
            aqi_color = aqi_result.get('color')
            dominant_pollutant = aqi_result.get('dominant_pollutant')
            
            # Create sensor reading
            with transaction.atomic():
                reading = SensorReading.objects.create(
                    user=self.config.user,
                    data=data,
                    temperature=temperature,
                    humidity=humidity,
                    co_ppm=co_ppm,
                    co2_ppm=co2_ppm,
                    ch4_ppm=ch4_ppm,
                    calculated_aqi=calculated_aqi,
                    aqi_category=aqi_category,
                    aqi_color=aqi_color,
                    dominant_pollutant=dominant_pollutant,
                )
                
                logger.info(
                    f"Saved sensor reading for user {self.config.user.email}: "
                    f"Temp={temperature}°C, Humidity={humidity}%, CO={co_ppm}ppm, AQI={calculated_aqi}"
                )
                
                self.command.stdout.write(
                    self.command.style.SUCCESS(
                        f"[OK] Saved reading for {self.config.user.email}: "
                        f"Temp={temperature}°C, AQI={calculated_aqi}"
                    )
                )
        
        except Exception as e:
            logger.error(f"Error saving sensor data for user {self.config.user.email}: {str(e)}", exc_info=True)
            self.command.stdout.write(
                self.command.style.ERROR(f"[ERROR] Error saving data for {self.config.user.email}: {str(e)}")
            )
    
    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker for user {self.config.user.email}: Return code {rc}")
            self.command.stdout.write(
                self.command.style.WARNING(
                    f"[WARN] Disconnected from {self.config.host}:{self.config.port} for user {self.config.user.email}"
                )
            )
        else:
            logger.info(f"Disconnected from MQTT broker for user {self.config.user.email}")
    
    def on_connect_fail(self, client, userdata):
        """Callback when connection fails"""
        self.connected = False
        logger.error(f"Connection failed to MQTT broker for user {self.config.user.email}: {self.config.host}:{self.config.port}")
        self.command.stdout.write(
            self.command.style.ERROR(
                f"[ERROR] Connection failed to {self.config.host}:{self.config.port} for user {self.config.user.email}"
            )
        )
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.create_client()
            self.client.connect(self.config.host, self.config.port, keepalive=60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker for user {self.config.user.email}: {str(e)}")
            self.command.stdout.write(
                self.command.style.ERROR(f"[ERROR] Connection error for {self.config.user.email}: {str(e)}")
            )
            self.connected = False
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            self.connected = False
    
    def reconnect(self):
        """Reconnect to MQTT broker with exponential backoff"""
        while not self.connected and self.config.is_active:
            try:
                self.disconnect()
                time.sleep(self.reconnect_delay)
                self.connect()
                
                # Wait a bit to see if connection succeeds
                time.sleep(2)
                
                if not self.connected:
                    # Exponential backoff
                    self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                    logger.warning(
                        f"Reconnection failed for user {self.config.user.email}, "
                        f"retrying in {self.reconnect_delay}s"
                    )
            except Exception as e:
                logger.error(f"Reconnection error for user {self.config.user.email}: {str(e)}")
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)


class Command(BaseCommand):
    help = 'Listen for MQTT sensor data from configured brokers'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clients = {}  # user_id -> MQTTClientWrapper
        self.running = True
        self.config_check_interval = 30  # Check for config changes every 30 seconds
        self.last_config_check = time.time()
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--check-interval',
            type=int,
            default=30,
            help='Interval in seconds to check for configuration changes (default: 30)',
        )
    
    def handle(self, *args, **options):
        self.config_check_interval = options.get('check_interval', 30)
        
        self.stdout.write(self.style.SUCCESS('Starting MQTT listener...'))
        logger.info('MQTT listener started')
        
        try:
            # Initial connection to all active configs
            self.update_clients()
            
            # Main loop: check for config changes and handle reconnections
            while self.running:
                time.sleep(5)  # Check every 5 seconds
                
                # Check for configuration changes periodically
                current_time = time.time()
                if current_time - self.last_config_check >= self.config_check_interval:
                    self.update_clients()
                    self.last_config_check = current_time
                
                # Check and reconnect disconnected clients
                self.check_reconnections()
        
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nShutting down MQTT listener...'))
            logger.info('MQTT listener shutting down')
            self.cleanup()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error in MQTT listener: {str(e)}'))
            logger.error(f'Error in MQTT listener: {str(e)}', exc_info=True)
            self.cleanup()
            raise
    
    def update_clients(self):
        """Update MQTT clients based on current configurations"""
        try:
            # Get all active configurations
            active_configs = MQTTBrokerConfig.objects.filter(is_active=True).select_related('user')
            
            # Get current user IDs
            current_user_ids = set(self.clients.keys())
            active_user_ids = {config.user.id for config in active_configs}
            
            # Remove clients for deactivated or deleted configs
            for user_id in current_user_ids - active_user_ids:
                if user_id in self.clients:
                    self.stdout.write(
                        self.style.WARNING(f"Removing MQTT client for user {user_id}")
                    )
                    self.clients[user_id].disconnect()
                    del self.clients[user_id]
            
            # Add or update clients for active configs
            for config in active_configs:
                user_id = config.user.id
                
                if user_id not in self.clients:
                    # New client
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Adding MQTT client for user {config.user.email}: "
                            f"{config.host}:{config.port}/{config.topic}"
                        )
                    )
                    wrapper = MQTTClientWrapper(config, self)
                    self.clients[user_id] = wrapper
                    wrapper.connect()
                else:
                    # Check if config changed
                    existing_config = self.clients[user_id].config
                    if (existing_config.host != config.host or
                        existing_config.port != config.port or
                        existing_config.topic != config.topic or
                        existing_config.username != config.username or
                        existing_config.password != config.password or
                        existing_config.client_id != config.client_id):
                        # Config changed, reconnect
                        self.stdout.write(
                            self.style.WARNING(
                                f"Configuration changed for user {config.user.email}, reconnecting..."
                            )
                        )
                        self.clients[user_id].disconnect()
                        wrapper = MQTTClientWrapper(config, self)
                        self.clients[user_id] = wrapper
                        wrapper.connect()
                    else:
                        # Update config reference (in case other fields changed)
                        self.clients[user_id].config = config
        
        except Exception as e:
            logger.error(f"Error updating clients: {str(e)}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f"Error updating clients: {str(e)}")
            )
    
    def check_reconnections(self):
        """Check and reconnect disconnected clients"""
        for user_id, wrapper in list(self.clients.items()):
            if not wrapper.connected and wrapper.config.is_active:
                # Try to reconnect
                wrapper.reconnect()
    
    def cleanup(self):
        """Clean up all MQTT connections"""
        self.running = False
        for wrapper in self.clients.values():
            wrapper.disconnect()
        self.clients.clear()
        self.stdout.write(self.style.SUCCESS('MQTT listener stopped'))


