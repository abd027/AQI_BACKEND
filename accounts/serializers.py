"""
Serializers for authentication and user management
"""
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    # Optional location fields (not stored in User model yet, but accepted to avoid validation errors)
    city = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    country = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'password', 'password_confirm', 'city', 'country', 'latitude', 'longitude')
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
        }
    
    def validate(self, attrs):
        """Validate that passwords match"""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password': 'Password fields do not match.'
            })
        return attrs
    
    def create(self, validated_data):
        """Create a new user and auto-subscribe to their city if provided"""
        validated_data.pop('password_confirm')
        # Extract location fields before creating user
        city = validated_data.pop('city', None)
        country = validated_data.pop('country', None)
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        
        user = User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password']
        )
        # Generate verification token
        user.generate_verification_token()
        
        # Auto-subscribe to city if location provided
        if city and country and latitude is not None and longitude is not None:
            try:
                from aqi.models import SavedLocation, CitySubscription
                
                # Create SavedLocation as primary location
                SavedLocation.objects.create(
                    user=user,
                    name=f"{city}, {country}",
                    city=city,
                    country=country,
                    latitude=latitude,
                    longitude=longitude
                )
                
                # Create CitySubscription for email notifications
                CitySubscription.objects.get_or_create(
                    user=user,
                    city=city,
                    country=country,
                    defaults={
                        'latitude': latitude,
                        'longitude': longitude,
                        'is_active': True
                    }
                )
            except Exception as e:
                # Log error but don't fail registration
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create subscription for user {user.email}: {e}")
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )


class TokenResponseSerializer(serializers.Serializer):
    """Serializer for JWT token response"""
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    token_type = serializers.CharField(default='Bearer')


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'role',
            'is_verified',
            'date_joined',
            'last_login'
        )
        read_only_fields = ('id', 'date_joined', 'last_login', 'role')


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request"""
    email = serializers.EmailField(required=True)


class PasswordResetSerializer(serializers.Serializer):
    """Serializer for password reset"""
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )


class EmailVerificationSerializer(serializers.Serializer):
    """Serializer for email verification"""
    token = serializers.CharField(required=True)

