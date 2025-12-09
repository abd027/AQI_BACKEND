"""
Tests for authentication endpoints
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from accounts.models import User
import secrets
from django.utils import timezone


@pytest.mark.django_db
@pytest.mark.auth
class TestUserRegistration:
    """Test user registration endpoint"""
    
    def test_valid_registration(self, api_client):
        """Test successful user registration"""
        url = reverse('accounts:register')
        data = {
            'email': 'newuser@example.com',
            'username': 'newuser',
            'password': 'securepass123',
            'password_confirm': 'securepass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data
        assert response.data['email'] == 'newuser@example.com'
        assert response.data['username'] == 'newuser'
        assert response.data['is_verified'] is False
        assert User.objects.filter(email='newuser@example.com').exists()
    
    def test_duplicate_email(self, api_client, test_user):
        """Test registration with duplicate email"""
        url = reverse('accounts:register')
        data = {
            'email': test_user.email,
            'username': 'differentuser',
            'password': 'securepass123',
            'password_confirm': 'securepass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_invalid_email_format(self, api_client):
        """Test registration with invalid email format"""
        url = reverse('accounts:register')
        data = {
            'email': 'invalid-email',
            'username': 'testuser',
            'password': 'securepass123',
            'password_confirm': 'securepass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_password_mismatch(self, api_client):
        """Test registration with mismatched passwords"""
        url = reverse('accounts:register')
        data = {
            'email': 'user@example.com',
            'username': 'testuser',
            'password': 'securepass123',
            'password_confirm': 'differentpass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_weak_password(self, api_client):
        """Test registration with weak password"""
        url = reverse('accounts:register')
        data = {
            'email': 'user@example.com',
            'username': 'testuser',
            'password': '123',
            'password_confirm': '123'
        }
        response = api_client.post(url, data, format='json')
        
        # Should fail validation (weak password)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_missing_required_fields(self, api_client):
        """Test registration with missing required fields"""
        url = reverse('accounts:register')
        data = {
            'email': 'user@example.com'
            # Missing username and password
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.auth
class TestUserLogin:
    """Test user login endpoint"""
    
    def test_valid_login(self, api_client, test_user):
        """Test successful login with valid credentials"""
        url = reverse('accounts:login')
        data = {
            'email': test_user.email,
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data
        assert 'refresh_token' in response.data
        assert 'token_type' in response.data
        assert response.data['token_type'] == 'Bearer'
    
    def test_invalid_email(self, api_client):
        """Test login with invalid email"""
        url = reverse('accounts:login')
        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
    
    def test_invalid_password(self, api_client, test_user):
        """Test login with invalid password"""
        url = reverse('accounts:login')
        data = {
            'email': test_user.email,
            'password': 'wrongpassword'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
    
    def test_inactive_account(self, api_client, inactive_user):
        """Test login with inactive account"""
        url = reverse('accounts:login')
        data = {
            'email': inactive_user.email,
            'password': 'testpass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert 'error' in response.data
    
    def test_missing_credentials(self, api_client):
        """Test login with missing credentials"""
        url = reverse('accounts:login')
        data = {}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.auth
class TestTokenRefresh:
    """Test token refresh endpoint"""
    
    def test_valid_refresh_token(self, api_client, test_user):
        """Test refreshing token with valid refresh token"""
        refresh = RefreshToken.for_user(test_user)
        url = reverse('accounts:refresh')
        data = {
            'refresh_token': str(refresh)
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.data
        assert 'refresh_token' in response.data
    
    def test_invalid_token_format(self, api_client):
        """Test refresh with invalid token format"""
        url = reverse('accounts:refresh')
        data = {
            'refresh_token': 'invalid.token.here'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_missing_token(self, api_client):
        """Test refresh with missing token"""
        url = reverse('accounts:refresh')
        data = {}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.auth
class TestUserLogout:
    """Test user logout endpoint"""
    
    def test_valid_logout(self, authenticated_client, test_user):
        """Test successful logout"""
        refresh = RefreshToken.for_user(test_user)
        url = reverse('accounts:logout')
        data = {
            'refresh_token': str(refresh)
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'detail' in response.data
    
    def test_invalid_token(self, authenticated_client):
        """Test logout with invalid token"""
        url = reverse('accounts:logout')
        data = {
            'refresh_token': 'invalid.token.here'
        }
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_missing_token(self, authenticated_client):
        """Test logout with missing token"""
        url = reverse('accounts:logout')
        data = {}
        response = authenticated_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_unauthenticated_logout(self, api_client):
        """Test logout without authentication"""
        url = reverse('accounts:logout')
        data = {
            'refresh_token': 'some.token'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
@pytest.mark.auth
class TestUserProfile:
    """Test user profile endpoint"""
    
    def test_get_current_user_authenticated(self, authenticated_client, test_user):
        """Test getting current user profile when authenticated"""
        url = reverse('accounts:me')
        response = authenticated_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == test_user.email
        assert response.data['username'] == test_user.username
    
    def test_get_current_user_unauthenticated(self, api_client):
        """Test getting current user profile when not authenticated"""
        url = reverse('accounts:me')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_update_profile(self, authenticated_client, test_user):
        """Test updating user profile"""
        url = reverse('accounts:me')
        data = {
            'username': 'updatedusername'
        }
        response = authenticated_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        test_user.refresh_from_db()
        assert test_user.username == 'updatedusername'


@pytest.mark.django_db
@pytest.mark.auth
class TestEmailVerification:
    """Test email verification endpoint"""
    
    def test_valid_verification_token(self, api_client, test_user):
        """Test email verification with valid token"""
        token = test_user.generate_verification_token()
        
        url = reverse('accounts:verify-email')
        response = api_client.post(url, {'token': token}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        test_user.refresh_from_db()
        assert test_user.is_verified is True
    
    def test_invalid_token(self, api_client):
        """Test email verification with invalid token"""
        url = reverse('accounts:verify-email')
        response = api_client.post(url, {'token': 'invalid_token'}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_already_verified_user(self, api_client, verified_user):
        """Test email verification for already verified user"""
        token = verified_user.generate_verification_token()
        
        url = reverse('accounts:verify-email')
        response = api_client.post(url, {'token': token}, format='json')
        
        # View returns 200 with message that email is already verified
        assert response.status_code == status.HTTP_200_OK
        assert 'already verified' in response.data.get('detail', '').lower()
    
    def test_missing_token(self, api_client):
        """Test email verification with missing token"""
        url = reverse('accounts:verify-email')
        response = api_client.post(url, {}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.auth
class TestResendVerification:
    """Test resend verification email endpoint"""
    
    def test_resend_verification_valid_email(self, api_client, test_user, mocker):
        """Test resending verification email with valid email"""
        mock_send = mocker.patch('accounts.views.send_verification_email')
        url = reverse('accounts:resend-verification')
        data = {
            'email': test_user.email
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'Verification email sent' in response.data.get('detail', '')
        mock_send.assert_called_once()
    
    def test_resend_verification_already_verified(self, api_client, verified_user, mocker):
        """Test resending verification email for already verified user"""
        mock_send = mocker.patch('accounts.views.send_verification_email')
        url = reverse('accounts:resend-verification')
        data = {
            'email': verified_user.email
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'already verified' in response.data.get('detail', '').lower()
        mock_send.assert_not_called()
    
    def test_resend_verification_invalid_email(self, api_client, mocker):
        """Test resending verification email with non-existent email"""
        mock_send = mocker.patch('accounts.views.send_verification_email')
        url = reverse('accounts:resend-verification')
        data = {
            'email': 'nonexistent@example.com'
        }
        response = api_client.post(url, data, format='json')
        
        # Should return 200 to prevent email enumeration
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_not_called()
    
    def test_resend_verification_missing_email(self, api_client):
        """Test resending verification email with missing email"""
        url = reverse('accounts:resend-verification')
        data = {}
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.auth
class TestPasswordReset:
    """Test password reset endpoints"""
    
    def test_forgot_password_valid_email(self, api_client, test_user, mocker):
        """Test forgot password with valid email"""
        mock_send = mocker.patch('accounts.views.send_password_reset_email')
        url = reverse('accounts:forgot-password')
        data = {
            'email': test_user.email
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        mock_send.assert_called_once()
    
    def test_forgot_password_invalid_email(self, api_client):
        """Test forgot password with non-existent email"""
        url = reverse('accounts:forgot-password')
        data = {
            'email': 'nonexistent@example.com'
        }
        response = api_client.post(url, data, format='json')
        
        # Should still return 200 to prevent email enumeration
        assert response.status_code == status.HTTP_200_OK
    
    def test_reset_password_valid_token(self, api_client, test_user):
        """Test password reset with valid token"""
        token = test_user.generate_password_reset_token()
        
        url = reverse('accounts:reset-password')
        data = {
            'token': token,
            'new_password': 'newsecurepass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        test_user.refresh_from_db()
        assert test_user.check_password('newsecurepass123')
    
    def test_reset_password_invalid_token(self, api_client):
        """Test password reset with invalid token"""
        url = reverse('accounts:reset-password')
        data = {
            'token': 'invalid_token',
            'new_password': 'newsecurepass123'
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_reset_password_missing_fields(self, api_client):
        """Test password reset with missing fields"""
        url = reverse('accounts:reset-password')
        data = {
            'token': 'some_token'
            # Missing new_password
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

