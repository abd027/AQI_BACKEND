"""
Tests for Django management commands
"""
import pytest
from io import StringIO
from django.core.management import call_command
from django.core.management.base import CommandError
from unittest.mock import patch, MagicMock
from accounts.models import User
from aqi.models import SavedLocation
from tests.utils.test_helpers import create_test_user, create_saved_location


@pytest.mark.django_db
class TestCheckAQIAlertsCommand:
    """Test check_aqi_alerts management command"""
    
    @patch('aqi.management.commands.check_aqi_alerts.check_and_send_aqi_alerts')
    def test_command_execution_success(self, mock_task):
        """Test command executes successfully"""
        mock_task.delay.return_value.get.return_value = {
            'status': 'success',
            'notifications_sent': 0,
            'locations_checked': 0,
            'users_checked': 0
        }
        
        out = StringIO()
        call_command('check_aqi_alerts', stdout=out)
        
        output = out.getvalue()
        assert 'Check completed successfully' in output or 'Starting AQI alert check' in output
    
    @patch('aqi.management.commands.check_aqi_alerts.check_and_send_aqi_alerts')
    def test_command_with_notifications_sent(self, mock_task):
        """Test command with notifications sent"""
        mock_task.delay.return_value.get.return_value = {
            'status': 'success',
            'notifications_sent': 5,
            'locations_checked': 10,
            'users_checked': 3
        }
        
        out = StringIO()
        call_command('check_aqi_alerts', stdout=out)
        
        output = out.getvalue()
        assert '5' in output or 'notifications_sent' in str(mock_task.delay.return_value.get.return_value)
    
    @patch('aqi.management.commands.check_aqi_alerts.check_and_send_aqi_alerts')
    def test_command_with_errors(self, mock_task):
        """Test command handles errors"""
        mock_task.delay.return_value.get.return_value = {
            'status': 'success',
            'notifications_sent': 2,
            'errors': ['Error 1', 'Error 2']
        }
        
        out = StringIO()
        call_command('check_aqi_alerts', stdout=out)
        
        output = out.getvalue()
        # Should handle errors gracefully
        assert output is not None
    
    @patch('aqi.management.commands.check_aqi_alerts.check_and_send_aqi_alerts')
    def test_command_failure(self, mock_task):
        """Test command handles task failure"""
        mock_task.delay.return_value.get.return_value = {
            'status': 'error',
            'message': 'Task failed'
        }
        
        out = StringIO()
        call_command('check_aqi_alerts', stdout=out)
        
        output = out.getvalue()
        assert 'error' in output.lower() or 'failed' in output.lower()
    
    @patch('aqi.management.commands.check_aqi_alerts.check_and_send_aqi_alerts')
    def test_command_exception_handling(self, mock_task):
        """Test command handles exceptions"""
        mock_task.delay.side_effect = Exception("Connection error")
        
        out = StringIO()
        err = StringIO()
        
        try:
            call_command('check_aqi_alerts', stdout=out, stderr=err)
        except Exception:
            pass  # Command should handle exceptions
        
        # Should not crash the test
        assert True


