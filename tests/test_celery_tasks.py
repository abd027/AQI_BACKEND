"""
Tests for Celery background tasks
"""
import pytest
from unittest.mock import patch, MagicMock, call
from django.utils import timezone
from django.core import mail
from aqi.tasks import check_and_send_aqi_alerts, AQI_THRESHOLD
from aqi.models import SavedLocation, AQINotification
from accounts.models import User
from tests.utils.test_helpers import create_test_user, create_saved_location


@pytest.mark.django_db
@pytest.mark.celery
class TestAQIAlertTasks:
    """Test AQI alert Celery tasks"""
    
    def test_task_with_no_saved_locations(self):
        """Test task when no saved locations exist"""
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'success'
        assert result['message'] == 'No saved locations to check'
        assert result['notifications_sent'] == 0
    
    @patch('aqi.tasks.aqi_service')
    def test_task_with_aqi_below_threshold(self, mock_service, test_user):
        """Test task when AQI is below threshold"""
        # Create saved location
        saved_location = create_saved_location(
            test_user,
            name='New York',
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Mock AQI service to return AQI below threshold
        # Note: tasks.py uses fetch_batch_current_aqi
        mock_service.fetch_batch_current_aqi.return_value = [
            {
                'location': {'lat': 40.7128, 'lon': -74.0060},
                'aqi': 45,  # Below threshold of 150
                'current': {'pm2_5': 12.5}
            }
        ]
        
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'success'
        assert result['notifications_sent'] == 0
        assert not AQINotification.objects.exists()
    
    @patch('aqi.tasks.send_aqi_alert_email')
    @patch('aqi.tasks.aqi_service')
    def test_task_with_aqi_above_threshold(self, mock_service, mock_send_email, test_user):
        """Test task when AQI exceeds threshold"""
        # Create saved location
        saved_location = create_saved_location(
            test_user,
            name='Delhi',
            latitude=28.6139,
            longitude=77.2090
        )
        
        # Mock AQI service to return AQI above threshold
        # Note: fetch_batch_current_aqi returns formatted data with 'aqi' as integer
        mock_service.fetch_batch_current_aqi.return_value = [
            {
                'location': {'lat': 28.6139, 'lon': 77.2090},
                'aqi': 155,  # Above threshold of 150 - must be integer, not dict
                'current': {'pm2_5': 55.0},
                'dominant_pollutant': 'pm2_5',
                'health_recommendations': ['Avoid outdoor activities']
            }
        ]
        
        mock_send_email.return_value = True
        
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'success'
        assert result['notifications_sent'] == 1
        assert AQINotification.objects.filter(
            user=test_user,
            saved_location=saved_location
        ).exists()
        mock_send_email.assert_called_once()
    
    @patch('aqi.tasks.send_aqi_alert_email')
    @patch('aqi.tasks.aqi_service')
    def test_daily_deduplication(self, mock_service, mock_send_email, test_user):
        """Test that notifications are only sent once per day per location"""
        saved_location = create_saved_location(
            test_user,
            name='Delhi',
            latitude=28.6139,
            longitude=77.2090
        )
        
        # Create existing notification for today
        AQINotification.objects.create(
            user=test_user,
            saved_location=saved_location,
            aqi_value=155,
            date=timezone.now().date()
        )
        
        # Mock AQI service to return AQI above threshold
        mock_service.fetch_batch_current_aqi.return_value = [
            {
                'location': {'lat': 28.6139, 'lon': 77.2090},
                'aqi': 160,  # Still above threshold
                'current': {'pm2_5': 60.0}
            }
        ]
        
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'success'
        assert result['notifications_sent'] == 0  # Should not send duplicate
        mock_send_email.assert_not_called()
    
    @patch('aqi.tasks.send_aqi_alert_email')
    @patch('aqi.tasks.aqi_service')
    def test_batch_processing(self, mock_service, mock_send_email):
        """Test batch processing of multiple locations"""
        # Create multiple users with saved locations
        user1 = create_test_user(email='user1@example.com', username='user1')
        user2 = create_test_user(email='user2@example.com', username='user2')
        
        location1 = create_saved_location(user1, name='Location1', latitude=40.7128, longitude=-74.0060)
        location2 = create_saved_location(user2, name='Location2', latitude=51.5074, longitude=-0.1278)
        
        # Mock AQI service to return high AQI for both
        # Note: 'aqi' must be integer, not dict
        mock_service.fetch_batch_current_aqi.return_value = [
            {
                'location': {'lat': 40.7128, 'lon': -74.0060},
                'aqi': 155,  # Integer value
                'current': {'pm2_5': 55.0},
                'dominant_pollutant': 'pm2_5',
                'health_recommendations': []
            },
            {
                'location': {'lat': 51.5074, 'lon': -0.1278},
                'aqi': 160,  # Integer value
                'current': {'pm2_5': 60.0},
                'dominant_pollutant': 'pm2_5',
                'health_recommendations': []
            }
        ]
        
        mock_send_email.return_value = True
        
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'success'
        assert result['notifications_sent'] == 2
        assert mock_send_email.call_count == 2
    
    @patch('aqi.tasks.aqi_service')
    def test_inactive_user_skipped(self, mock_service, inactive_user):
        """Test that inactive users are skipped"""
        saved_location = create_saved_location(
            inactive_user,
            name='Location',
            latitude=40.7128,
            longitude=-74.0060
        )
        
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'success'
        assert result['notifications_sent'] == 0
        mock_service.fetch_batch_current_aqi.assert_not_called()
    
    @patch('aqi.tasks.aqi_service')
    def test_api_failure_handling(self, mock_service, test_user):
        """Test error handling when API fails"""
        saved_location = create_saved_location(
            test_user,
            name='Location',
            latitude=40.7128,
            longitude=-74.0060
        )
        
        # Mock API to return None (failure)
        mock_service.fetch_batch_current_aqi.return_value = None
        
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'error'
        assert result['message'] == 'Failed to fetch AQI data from API'
        assert result['notifications_sent'] == 0
    
    @patch('aqi.tasks.send_aqi_alert_email')
    @patch('aqi.tasks.aqi_service')
    def test_email_send_failure(self, mock_service, mock_send_email, test_user):
        """Test handling when email sending fails"""
        saved_location = create_saved_location(
            test_user,
            name='Delhi',
            latitude=28.6139,
            longitude=77.2090
        )
        
        mock_service.fetch_batch_current_aqi.return_value = [
            {
                'location': {'lat': 28.6139, 'lon': 77.2090},
                'aqi': 155,  # Integer value
                'current': {'pm2_5': 55.0},
                'dominant_pollutant': 'pm2_5',
                'health_recommendations': []
            }
        ]
        
        # Mock email sending to fail
        mock_send_email.return_value = False
        
        result = check_and_send_aqi_alerts()
        
        assert result['status'] == 'success'
        assert result['notifications_sent'] == 0  # Should not count failed emails
        assert 'errors' in result or result['notifications_sent'] == 0


@pytest.mark.django_db
@pytest.mark.celery
class TestEmailNotifications:
    """Test email notification functionality"""
    
    @patch('aqi.utils.send_mail')
    def test_email_sending_function(self, mock_send_mail, test_user, saved_location):
        """Test email sending function"""
        from aqi.utils import send_aqi_alert_email
        
        aqi_data = {
            'aqi': {
                'local_epa_aqi': {
                    'value': 155,
                    'category': 'Unhealthy'
                }
            },
            'dominant_pollutant': 'pm2_5',
            'health_recommendations': ['Avoid outdoor activities']
        }
        
        result = send_aqi_alert_email(test_user, saved_location, 155, aqi_data)
        
        assert result is True
        mock_send_mail.assert_called_once()
        assert mock_send_mail.call_args[1]['recipient_list'] == [test_user.email]
    
    @patch('aqi.utils.send_mail')
    def test_email_template_rendering(self, mock_send_mail, test_user, saved_location):
        """Test email template rendering"""
        from aqi.utils import send_aqi_alert_email
        
        aqi_data = {
            'aqi': {
                'local_epa_aqi': {
                    'value': 155,
                    'category': 'Unhealthy'
                }
            },
            'dominant_pollutant': 'pm2_5',
            'health_recommendations': ['Stay indoors', 'Use air purifier']
        }
        
        send_aqi_alert_email(test_user, saved_location, 155, aqi_data)
        
        # Verify email was sent with proper subject
        call_args = mock_send_mail.call_args
        assert 'Air Quality Alert' in call_args[1]['subject'] or 'AQI' in call_args[1]['subject']
        assert saved_location.name in call_args[1]['subject']
    
    @patch('aqi.utils.send_mail')
    def test_email_failure_handling(self, mock_send_mail, test_user, saved_location):
        """Test email failure handling"""
        from aqi.utils import send_aqi_alert_email
        
        # Mock send_mail to raise exception
        mock_send_mail.side_effect = Exception("SMTP Error")
        
        aqi_data = {
            'aqi': {
                'local_epa_aqi': {
                    'value': 155,
                    'category': 'Unhealthy'
                }
            },
            'dominant_pollutant': 'pm2_5',
            'health_recommendations': []
        }
        
        result = send_aqi_alert_email(test_user, saved_location, 155, aqi_data)
        
        assert result is False

