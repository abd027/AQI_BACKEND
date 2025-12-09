"""
Utility functions for AQI app, including email notifications
"""
from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags
from core.utils import get_aqi_category


def send_aqi_alert_email(user, saved_location, aqi_value, aqi_data):
    """
    Send AQI alert email to user when air quality exceeds threshold
    
    Args:
        user: User instance
        saved_location: SavedLocation instance
        aqi_value: Current AQI value (float)
        aqi_data: Full AQI data dictionary from OpenMeteoAQIService
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    # Get AQI category information
    aqi_info = get_aqi_category(aqi_value) if aqi_value else {
        'category': 'Unknown',
        'color': '#808080',
        'health_advice': 'Unable to determine air quality.'
    }
    
    # Prepare location name
    location_name = saved_location.name
    if saved_location.city:
        location_name = f"{saved_location.city}, {saved_location.country}" if saved_location.country else saved_location.city
    
    # Get health recommendations from aqi_data if available
    health_recommendations = aqi_data.get('health_recommendations', [])
    if not health_recommendations and aqi_info.get('health_advice'):
        health_recommendations = [aqi_info['health_advice']]
    
    # Build health recommendations HTML
    recommendations_html = ""
    if health_recommendations:
        recommendations_html = "<ul>"
        for rec in health_recommendations:
            recommendations_html += f"<li>{rec}</li>"
        recommendations_html += "</ul>"
    else:
        recommendations_html = f"<p>{aqi_info.get('health_advice', 'Please check air quality conditions before going outside.')}</p>"
    
    # Get dominant pollutant if available
    dominant_pollutant = aqi_data.get('dominant_pollutant', 'Unknown')
    pollutant_display = {
        'pm25': 'PM2.5',
        'pm2_5': 'PM2.5',
        'pm10': 'PM10',
        'o3': 'Ozone',
        'no2': 'Nitrogen Dioxide',
        'co': 'Carbon Monoxide',
        'so2': 'Sulphur Dioxide',
    }.get(dominant_pollutant, dominant_pollutant.replace('_', ' ').title())
    
    # Build frontend URL to view details
    view_url = f"{settings.FRONTEND_URL}/map?lat={saved_location.latitude}&lon={saved_location.longitude}"
    
    # Email subject
    subject = f'⚠️ Air Quality Alert: {location_name} - AQI {int(aqi_value)}'
    
    # HTML email template
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: {aqi_info.get('color', '#808080')};
                color: white;
                padding: 20px;
                border-radius: 5px 5px 0 0;
                text-align: center;
            }}
            .content {{
                background-color: #f9f9f9;
                padding: 20px;
                border: 1px solid #ddd;
                border-top: none;
                border-radius: 0 0 5px 5px;
            }}
            .aqi-value {{
                font-size: 48px;
                font-weight: bold;
                margin: 10px 0;
            }}
            .category {{
                font-size: 24px;
                margin: 10px 0;
            }}
            .info-section {{
                background-color: white;
                padding: 15px;
                margin: 15px 0;
                border-radius: 5px;
                border-left: 4px solid {aqi_info.get('color', '#808080')};
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: {aqi_info.get('color', '#808080')};
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin: 20px 0;
            }}
            .footer {{
                margin-top: 20px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                font-size: 12px;
                color: #666;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚠️ Air Quality Alert</h1>
        </div>
        <div class="content">
            <h2>Hi {user.username},</h2>
            <p>The air quality in <strong>{location_name}</strong> has exceeded the unhealthy threshold.</p>
            
            <div class="info-section">
                <div class="aqi-value" style="color: {aqi_info.get('color', '#808080')};">{int(aqi_value)}</div>
                <div class="category" style="color: {aqi_info.get('color', '#808080')};">{aqi_info.get('category', 'Unknown')}</div>
            </div>
            
            <div class="info-section">
                <h3>Location Details</h3>
                <p><strong>Location:</strong> {location_name}</p>
                <p><strong>Coordinates:</strong> {saved_location.latitude:.4f}, {saved_location.longitude:.4f}</p>
                <p><strong>Dominant Pollutant:</strong> {pollutant_display}</p>
            </div>
            
            <div class="info-section">
                <h3>Health Recommendations</h3>
                {recommendations_html}
            </div>
            
            <div style="text-align: center;">
                <a href="{view_url}" class="button">View Air Quality Details</a>
            </div>
            
            <div class="footer">
                <p>This is an automated alert from BreatheEasy. You will receive at most one alert per day per location when air quality exceeds 100.</p>
                <p>Stay safe and take necessary precautions.</p>
                <p>Best regards,<br>The BreatheEasy Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version
    plain_message = f"""
Air Quality Alert - {location_name}

Hi {user.username},

The air quality in {location_name} has exceeded the unhealthy threshold.

Current AQI: {int(aqi_value)}
Category: {aqi_info.get('category', 'Unknown')}
Dominant Pollutant: {pollutant_display}

Location: {location_name}
Coordinates: {saved_location.latitude:.4f}, {saved_location.longitude:.4f}

Health Recommendations:
{chr(10).join(['- ' + rec for rec in health_recommendations]) if health_recommendations else aqi_info.get('health_advice', 'Please check air quality conditions before going outside.')}

View details: {view_url}

This is an automated alert from BreatheEasy. You will receive at most one alert per day per location when air quality exceeds 100.

Stay safe and take necessary precautions.

Best regards,
The BreatheEasy Team
    """
    
    try:
        send_mail(
            subject=subject,
            message=strip_tags(plain_message),
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending AQI alert email to {user.email}: {e}")
        return False

