"""
API views for city subscription management
"""
import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from .models import CitySubscription, SavedLocation
from .serializers import CitySubscriptionSerializer
from .services import OpenMeteoAQIService
from .utils import send_aqi_alert_email

logger = logging.getLogger(__name__)


class NoPagination(PageNumberPagination):
    """Disable pagination for subscriptions"""
    page_size = None


class CitySubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing city subscriptions
    
    GET /api/aqi/subscriptions/ - List user's subscriptions
    POST /api/aqi/subscriptions/ - Create new subscription
    GET /api/aqi/subscriptions/{id}/ - Get subscription details
    PATCH /api/aqi/subscriptions/{id}/ - Update subscription
    DELETE /api/aqi/subscriptions/{id}/ - Delete subscription
    """
    serializer_class = CitySubscriptionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = NoPagination
    
    def get_queryset(self):
        """Return subscriptions for the current user"""
        return CitySubscription.objects.filter(user=self.request.user)
    
    @action(detail=True, methods=['patch'])
    def toggle(self, request, pk=None):
        """Toggle subscription active status"""
        subscription = self.get_object()
        subscription.is_active = not subscription.is_active
        subscription.save()
        
        serializer = self.get_serializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='send_notification')
    def send_notification(self, request, pk=None):
        """
        Send an immediate email notification for this subscription
        Fetches current AQI data and sends email to the user
        
        Accepts optional 'aqi_value' in request body to use the AQI value
        displayed in the frontend card for consistency.
        """
        subscription = self.get_object()
        
        try:
            logger.info(f"Starting notification send for subscription {subscription.id} (user: {request.user.email})")
            
            # Check if AQI value is provided in request body (from frontend)
            provided_aqi_value = request.data.get('aqi_value')
            
            aqi_service = OpenMeteoAQIService()
            
            # Fetch current AQI data for email content (always needed for full data)
            logger.info(f"Fetching AQI data for lat={subscription.latitude}, lon={subscription.longitude}")
            aqi_data = aqi_service.fetch_current_aqi(
                subscription.latitude,
                subscription.longitude
            )
            
            if not aqi_data:
                logger.error(f"No AQI data returned for subscription {subscription.id}")
                return Response(
                    {'error': 'Unable to fetch AQI data for this location. Please try again later.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Use provided AQI value if available (from frontend card), otherwise use fetched value
            if provided_aqi_value is not None:
                # Round to integer to match what's displayed in the card
                aqi_value = round(float(provided_aqi_value))
                logger.info(f"Using provided AQI value: {aqi_value} for subscription {subscription.id} (from frontend card - matches displayed value)")
                # Update aqi_data with the provided value to ensure consistency
                aqi_data['aqi'] = aqi_value
            else:
                # Extract AQI value from fetched data (backward compatibility)
                aqi_value = aqi_data.get('aqi')
                if aqi_value is None:
                    logger.error(f"AQI value missing in response for subscription {subscription.id}")
                    return Response(
                        {'error': 'AQI data is incomplete. Please try again later.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                logger.info(f"Retrieved AQI value: {aqi_value} for subscription {subscription.id} (from API)")
            
            # Get or create SavedLocation for email sending
            # (email function expects SavedLocation)
            saved_location, created = SavedLocation.objects.get_or_create(
                user=request.user,
                latitude=subscription.latitude,
                longitude=subscription.longitude,
                defaults={
                    'name': f"{subscription.city}, {subscription.country or ''}",
                    'city': subscription.city,
                    'country': subscription.country,
                }
            )
            
            if created:
                logger.info(f"Created new SavedLocation for subscription {subscription.id}")
            else:
                logger.info(f"Using existing SavedLocation for subscription {subscription.id}")
            
            # Send email notification
            logger.info(f"Attempting to send email to {request.user.email}")
            email_sent = send_aqi_alert_email(
                user=request.user,
                saved_location=saved_location,
                aqi_value=aqi_value,
                aqi_data=aqi_data
            )
            
            if email_sent:
                logger.info(f"Email sent successfully to {request.user.email} for subscription {subscription.id}")
                return Response({
                    'success': True,
                    'message': f'Notification sent successfully. Current AQI: {int(aqi_value)}',
                    'aqi_value': aqi_value
                })
            else:
                logger.error(f"Email sending failed for {request.user.email} (subscription {subscription.id})")
                return Response(
                    {'error': 'Failed to send email notification. Please check your email configuration.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Exception as e:
            logger.error(f"Exception in send_notification for subscription {subscription.id}: {str(e)}", exc_info=True)
            return Response(
                {'error': f'Error sending notification: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def perform_create(self, serializer):
        """Create subscription for the current user"""
        serializer.save(user=self.request.user)

