"""
Celery tasks for AQI monitoring and notifications
"""
import logging
from collections import defaultdict
from django.utils import timezone
from celery import shared_task
from accounts.models import User
from .models import SavedLocation, AQINotification, CitySubscription
from .services import OpenMeteoAQIService
from .waqi_service import WAQIService
from .cache import set_cached_city_rankings
from .utils import send_aqi_alert_email

logger = logging.getLogger(__name__)

# Initialize AQI services
aqi_service = OpenMeteoAQIService()
waqi_service = WAQIService()

# AQI threshold for alerts
AQI_THRESHOLD = 100


@shared_task(bind=True, name='aqi.tasks.check_and_send_aqi_alerts')
def check_and_send_aqi_alerts(self):
    """
    Periodic task to check AQI for all user city subscriptions and send email alerts
    when AQI exceeds threshold (100).
    
    This task:
    1. Fetches all active city subscriptions
    2. Groups locations by coordinates to batch API calls
    3. Fetches current AQI for all unique locations
    4. Checks if AQI >= 100 and if notification already sent today
    5. Sends email alerts and creates notification records
    """
    logger.info("Starting AQI alert check task")
    
    try:
        # Get today's date for deduplication
        today = timezone.now().date()
        
        # Fetch all active city subscriptions with their users
        subscriptions = CitySubscription.objects.select_related('user').filter(is_active=True)
        
        if not subscriptions.exists():
            logger.info("No active subscriptions found. Skipping AQI check.")
            return {
                'status': 'success',
                'message': 'No active subscriptions to check',
                'notifications_sent': 0
            }
        
        # Group locations by coordinates to minimize API calls
        # Use tuple of (lat, lon) as key, store list of (user, subscription) pairs
        location_groups = defaultdict(list)
        
        for subscription in subscriptions:
            # Only check active users
            if not subscription.user.is_active:
                continue
            
            key = (round(subscription.latitude, 4), round(subscription.longitude, 4))
            location_groups[key].append((subscription.user, subscription))
        
        if not location_groups:
            logger.info("No active users with subscriptions. Skipping AQI check.")
            return {
                'status': 'success',
                'message': 'No active users with subscriptions',
                'notifications_sent': 0
            }
        
        # Prepare batch request for unique locations
        unique_locations = [
            {'lat': lat, 'lon': lon}
            for lat, lon in location_groups.keys()
        ]
        
        logger.info(f"Fetching AQI for {len(unique_locations)} unique locations")
        
        # Fetch AQI data for all unique locations in batch
        aqi_results = aqi_service.fetch_batch_current_aqi(unique_locations)
        
        if not aqi_results:
            logger.error("Failed to fetch AQI data from API")
            return {
                'status': 'error',
                'message': 'Failed to fetch AQI data from API',
                'notifications_sent': 0
            }
        
        # Process results and send notifications
        notifications_sent = 0
        errors = []
        
        # Create mapping from coordinates to AQI data
        location_aqi_map = {}
        for i, (lat, lon) in enumerate(location_groups.keys()):
            if i < len(aqi_results):
                location_aqi_map[(lat, lon)] = aqi_results[i]
        
        # Process each location group
        for (lat, lon), user_location_pairs in location_groups.items():
            aqi_data = location_aqi_map.get((lat, lon))
            
            if not aqi_data:
                logger.warning(f"No AQI data for location ({lat}, {lon})")
                continue
            
            # Get AQI value from the data
            aqi_value = aqi_data.get('aqi')
            
            if aqi_value is None:
                logger.warning(f"AQI value is None for location ({lat}, {lon})")
                continue
            
            # Check if AQI exceeds threshold
            if aqi_value < AQI_THRESHOLD:
                continue  # Skip locations with AQI < 100
            
            # Process each user-subscription pair for this coordinate
            for user, subscription in user_location_pairs:
                try:
                    # Get or create SavedLocation for email sending (email function expects SavedLocation)
                    saved_location, created = SavedLocation.objects.get_or_create(
                        user=user,
                        latitude=subscription.latitude,
                        longitude=subscription.longitude,
                        defaults={
                            'name': f"{subscription.city}, {subscription.country}",
                            'city': subscription.city,
                            'country': subscription.country,
                        }
                    )
                    
                    # Check if notification already sent today for this user-subscription
                    existing_notification = AQINotification.objects.filter(
                        user=user,
                        saved_location=saved_location,
                        date=today
                    ).exists()
                    
                    if existing_notification:
                        logger.debug(
                            f"Notification already sent today for user {user.email} "
                            f"for subscription {subscription.city}, {subscription.country} (AQI: {aqi_value})"
                        )
                        continue
                    
                    # Send email notification
                    logger.info(
                        f"Sending AQI alert to {user.email} for subscription {subscription.city}, {subscription.country} "
                        f"(AQI: {aqi_value})"
                    )
                    
                    email_sent = send_aqi_alert_email(
                        user=user,
                        saved_location=saved_location,
                        aqi_value=aqi_value,
                        aqi_data=aqi_data
                    )
                    
                    if email_sent:
                        # Create notification record
                        AQINotification.objects.create(
                            user=user,
                            saved_location=saved_location,
                            aqi_value=aqi_value,
                            date=today
                        )
                        notifications_sent += 1
                        logger.info(
                            f"Successfully sent AQI alert to {user.email} for {subscription.city}, {subscription.country}"
                        )
                    else:
                        logger.error(
                            f"Failed to send email to {user.email} for subscription {subscription.city}, {subscription.country}"
                        )
                        errors.append(f"Email send failed for {user.email} - {subscription.city}, {subscription.country}")
                
                except Exception as e:
                    error_msg = f"Error processing notification for {user.email} - {saved_location.name}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    errors.append(error_msg)
                    # Continue processing other users/locations even if one fails
        
        result = {
            'status': 'success',
            'notifications_sent': notifications_sent,
            'locations_checked': len(unique_locations),
            'users_checked': len(set(user for pairs in location_groups.values() for user, _ in pairs))
        }
        
        if errors:
            result['errors'] = errors
            result['error_count'] = len(errors)
        
        logger.info(
            f"AQI alert check completed. Sent {notifications_sent} notifications, "
            f"checked {len(unique_locations)} locations"
        )
        
        return result
    
    except Exception as e:
        error_msg = f"Critical error in AQI alert check task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'error',
            'message': error_msg,
            'notifications_sent': 0
        }


@shared_task(bind=True, name='aqi.tasks.refresh_waqi_city_rankings')
def refresh_waqi_city_rankings(self):
    """
    Periodic task to refresh WAQI city rankings cache
    
    This task:
    1. Fetches latest city rankings from WAQI API
    2. Updates the cache with fresh data
    3. Runs every 15-60 minutes (configured in Celery beat schedule)
    """
    logger.info("Starting WAQI city rankings refresh task")
    
    try:
        # Build rankings from WAQI API
        rankings = waqi_service.build_worst_aqi_rankings(top_n=30)
        
        if not rankings:
            logger.warning("No rankings returned from WAQI service")
            return {
                'status': 'error',
                'message': 'No rankings returned from WAQI service',
                'cities_count': 0
            }
        
        # Update cache with fresh data
        cache_success = set_cached_city_rankings(rankings)
        
        if not cache_success:
            logger.error("Failed to cache city rankings")
            return {
                'status': 'error',
                'message': 'Failed to cache city rankings',
                'cities_count': len(rankings)
            }
        
        logger.info(
            f"Successfully refreshed WAQI city rankings cache with {len(rankings)} cities"
        )
        
        return {
            'status': 'success',
            'message': 'City rankings cache refreshed successfully',
            'cities_count': len(rankings)
        }
        
    except Exception as e:
        error_msg = f"Critical error in WAQI city rankings refresh task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            'status': 'error',
            'message': error_msg,
            'cities_count': 0
        }

