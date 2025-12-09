"""
Utility functions for authentication
"""
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_verification_email(user):
    """
    Send email verification email to user
    
    Args:
        user: User instance
    """
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={user.verification_token}"
    
    subject = 'Verify your BreatheEasy account'
    html_message = f"""
    <html>
    <body>
        <h2>Welcome to BreatheEasy!</h2>
        <p>Hi {user.username},</p>
        <p>Thank you for registering. Please verify your email address by clicking the link below:</p>
        <p><a href="{verification_url}">Verify Email</a></p>
        <p>Or copy and paste this URL into your browser:</p>
        <p>{verification_url}</p>
        <p>If you didn't create an account, please ignore this email.</p>
        <p>Best regards,<br>The BreatheEasy Team</p>
    </body>
    </html>
    """
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending verification email: {e}")
        return False


def send_password_reset_email(user):
    """
    Send password reset email to user
    
    Args:
        user: User instance
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={user.password_reset_token}"
    
    subject = 'Reset your BreatheEasy password'
    html_message = f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>Hi {user.username},</p>
        <p>You requested to reset your password. Click the link below to reset it:</p>
        <p><a href="{reset_url}">Reset Password</a></p>
        <p>Or copy and paste this URL into your browser:</p>
        <p>{reset_url}</p>
        <p>This link will expire in 1 hour.</p>
        <p>If you didn't request a password reset, please ignore this email.</p>
        <p>Best regards,<br>The BreatheEasy Team</p>
    </body>
    </html>
    """
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending password reset email: {e}")
        return False

