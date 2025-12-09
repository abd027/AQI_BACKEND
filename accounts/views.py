"""
Authentication views for user registration, login, and token management
"""
from rest_framework import status, generics, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.contrib.auth import authenticate
from django.utils import timezone
from .models import User
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    TokenResponseSerializer,
    UserProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetSerializer,
    EmailVerificationSerializer,
)
from .utils import send_verification_email, send_password_reset_email


class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Register a new user
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = UserRegistrationSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Send verification email
        send_verification_email(user)
        
        return Response(
            {
                'id': str(user.id),
                'email': user.email,
                'username': user.username,
                'is_active': user.is_active,
                'is_verified': user.is_verified,
                'created_at': user.date_joined.isoformat(),
            },
            status=status.HTTP_201_CREATED
        )


class LoginView(generics.GenericAPIView):
    """
    POST /api/auth/login/
    Login user and return JWT tokens
    """
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        user = authenticate(request, username=email, password=password)
        
        if not user:
            return Response(
                {'error': True, 'detail': 'Invalid email or password.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': True, 'detail': 'User account is disabled.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'token_type': 'Bearer'
        })


class RefreshTokenView(generics.GenericAPIView):
    """
    POST /api/auth/refresh/
    Refresh access token using refresh token
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response(
                {'error': True, 'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refresh = RefreshToken(refresh_token)
            access_token = refresh.access_token
            
            return Response({
                'access_token': str(access_token),
                'refresh_token': str(refresh),
                'token_type': 'Bearer'
            })
        except Exception as e:
            return Response(
                {'error': True, 'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(generics.GenericAPIView):
    """
    POST /api/auth/logout/
    Logout user and blacklist refresh token
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response(
                {'error': True, 'detail': 'Refresh token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {'detail': 'Successfully logged out.'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': True, 'detail': 'Invalid refresh token.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    GET /api/auth/me/
    Get current user profile
    
    PATCH /api/auth/me/
    Update current user profile
    """
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    def get_object(self):
        return self.request.user


class VerifyEmailView(generics.GenericAPIView):
    """
    POST /api/auth/verify-email/?token=<token>
    Verify user email address
    """
    permission_classes = [AllowAny]
    serializer_class = EmailVerificationSerializer
    
    def post(self, request, *args, **kwargs):
        token = request.query_params.get('token') or request.data.get('token')
        
        if not token:
            return Response(
                {'error': True, 'detail': 'Verification token is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(verification_token=token)
            
            if user.is_verified:
                return Response(
                    {'detail': 'Email is already verified.'},
                    status=status.HTTP_200_OK
                )
            
            user.is_verified = True
            user.verification_token = None
            user.verification_token_created = None
            user.save(update_fields=['is_verified', 'verification_token', 'verification_token_created'])
            
            return Response(
                {'detail': 'Email successfully verified.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': True, 'detail': 'Invalid verification token.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error verifying email: {str(e)}", exc_info=True)
            
            # Always return JSON, even on unexpected errors
            return Response(
                {'error': True, 'detail': 'An error occurred during email verification. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResendVerificationView(generics.GenericAPIView):
    """
    POST /api/auth/resend-verification/
    Resend verification email
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        
        if not email:
            return Response(
                {'error': True, 'detail': 'Email is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            
            if user.is_verified:
                return Response(
                    {'detail': 'Email is already verified.'},
                    status=status.HTTP_200_OK
                )
            
            # Generate new token and send email
            user.generate_verification_token()
            send_verification_email(user)
            
            return Response(
                {'detail': 'Verification email sent.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return Response(
                {'detail': 'If the email exists, a verification email has been sent.'},
                status=status.HTTP_200_OK
            )


class ForgotPasswordView(generics.GenericAPIView):
    """
    POST /api/auth/forgot-password/
    Request password reset
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetRequestSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            user.generate_password_reset_token()
            send_password_reset_email(user)
            
            return Response(
                {'detail': 'If the email exists, a password reset email has been sent.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return Response(
                {'detail': 'If the email exists, a password reset email has been sent.'},
                status=status.HTTP_200_OK
            )


class ResetPasswordView(generics.GenericAPIView):
    """
    POST /api/auth/reset-password/
    Reset password using token
    """
    permission_classes = [AllowAny]
    serializer_class = PasswordResetSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            user = User.objects.get(password_reset_token=token)
            
            if not user.is_password_reset_token_valid(token):
                return Response(
                    {'error': True, 'detail': 'Invalid or expired password reset token.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            user.set_password(new_password)
            user.clear_password_reset_token()
            user.save()
            
            return Response(
                {'detail': 'Password successfully reset.'},
                status=status.HTTP_200_OK
            )
        except User.DoesNotExist:
            return Response(
                {'error': True, 'detail': 'Invalid password reset token.'},
                status=status.HTTP_400_BAD_REQUEST
            )
