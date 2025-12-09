"""
Shared utility functions
"""
import requests
from typing import Optional, Tuple, Dict, Any


def geocode_city(city_name: str) -> Optional[Tuple[float, float]]:
    """
    Geocode a city name to latitude and longitude using Open-Meteo Geocoding API
    
    Args:
        city_name: Name of the city
        
    Returns:
        Tuple of (latitude, longitude) or None if not found
    """
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            'name': city_name,
            'count': 1,
            'language': 'en',
            'format': 'json'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('results') and len(data['results']) > 0:
            result = data['results'][0]
            return (result['latitude'], result['longitude'])
        
        return None
    except Exception as e:
        print(f"Error geocoding city {city_name}: {e}")
        return None


def search_city(city_name: str) -> Optional[Dict[str, Any]]:
    """
    Search for a city and return detailed location info
    
    Args:
        city_name: Name of the city
        
    Returns:
        Dict with name, latitude, longitude, country, etc. or None
    """
    try:
        url = "https://geocoding-api.open-meteo.com/v1/search"
        params = {
            'name': city_name,
            'count': 1,
            'language': 'en',
            'format': 'json'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('results') and len(data['results']) > 0:
            result = data['results'][0]
            return {
                'name': result.get('name'),
                'latitude': result.get('latitude'),
                'longitude': result.get('longitude'),
                'country': result.get('country'),
                'country_code': result.get('country_code'),
                'admin1': result.get('admin1'),
            }
        
        return None
    except Exception as e:
        print(f"Error searching city {city_name}: {e}")
        return None


def reverse_geocode(latitude: float, longitude: float) -> Optional[Dict[str, str]]:
    """
    Reverse geocode coordinates to get city name and country using Open-Meteo Geocoding API
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        
    Returns:
        Dict with city and country or None if not found
    """
    try:
        # Use Nominatim API for reverse geocoding (free, no API key required)
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': latitude,
            'lon': longitude,
            'format': 'json',
            'addressdetails': 1
        }
        headers = {
            'User-Agent': 'BreatheEasy-AQI-App/1.0'  # Required by Nominatim
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Try to get city name from address components
        address = data.get('address', {})
        city = (
            address.get('city') or 
            address.get('town') or 
            address.get('village') or 
            address.get('municipality') or
            address.get('county')
        )
        
        country = address.get('country')
        
        if city:
            return {'city': city, 'country': country}
        
        return None
    except Exception as e:
        print(f"Error reverse geocoding ({latitude}, {longitude}): {e}")
        return None


def calculate_epa_aqi(pollutant: str, concentration: float) -> Optional[int]:
    """
    Calculate EPA AQI for a given pollutant and concentration
    
    Args:
        pollutant: One of 'pm25', 'pm10', 'o3', 'no2', 'co', 'so2'
        concentration: Pollutant concentration in appropriate units
        
    Returns:
        AQI value (0-500) or None if invalid
    """
    # EPA AQI breakpoints (simplified version)
    # For production, use the full EPA AQI calculation tables
    
    aqi_breakpoints = {
        'pm25': [
            (0, 12.0, 0, 50),
            (12.1, 35.4, 51, 100),
            (35.5, 55.4, 101, 150),
            (55.5, 150.4, 151, 200),
            (150.5, 250.4, 201, 300),
            (250.5, 350.4, 301, 400),
            (350.5, 500.4, 401, 500),
        ],
        'pm10': [
            (0, 54, 0, 50),
            (55, 154, 51, 100),
            (155, 254, 101, 150),
            (255, 354, 151, 200),
            (355, 424, 201, 300),
            (425, 504, 301, 400),
            (505, 604, 401, 500),
        ],
        'o3': [
            (0, 54, 0, 50),
            (55, 70, 51, 100),
            (71, 85, 101, 150),
            (86, 105, 151, 200),
            (106, 200, 201, 300),
            (201, 400, 301, 400), # Extended range
        ],
        'no2': [
            (0, 53, 0, 50),
            (54, 100, 51, 100),
            (101, 360, 101, 150),
            (361, 649, 151, 200),
            (650, 1249, 201, 300),
            (1250, 2049, 301, 400),
        ],
        'so2': [
            (0, 35, 0, 50),
            (36, 75, 51, 100),
            (76, 185, 101, 150),
            (186, 304, 151, 200),
            (305, 604, 201, 300),
            (605, 1004, 301, 400),
        ],
        'co': [
            (0, 4400, 0, 50),
            (4401, 9400, 51, 100),
            (9401, 12400, 101, 150),
            (12401, 15400, 151, 200),
            (15401, 30400, 201, 300),
            (30401, 50400, 301, 400),
        ],
    }
    
    if pollutant.lower() not in aqi_breakpoints:
        return None
    
    breakpoints = aqi_breakpoints[pollutant.lower()]
    
    for c_low, c_high, aqi_low, aqi_high in breakpoints:
        if c_low <= concentration <= c_high:
            # Linear interpolation
            aqi = ((aqi_high - aqi_low) / (c_high - c_low)) * (concentration - c_low) + aqi_low
            return int(round(aqi))
    
    # If concentration exceeds highest breakpoint, return 500
    if concentration > breakpoints[-1][1]:
        return 500
    
    return None


def calculate_indoor_aqi(co_ppm: Optional[float] = None, 
                         co2_ppm: Optional[float] = None, 
                         ch4_ppm: Optional[float] = None) -> dict:
    """
    Calculate indoor air quality index from MQ sensor readings
    
    This function uses realistic indoor air quality thresholds for:
    - CO (Carbon Monoxide) from MQ-7 sensor
    - CO2 (Carbon Dioxide) from MQ-135 sensor  
    - CH4 (Methane) from MQ-4 sensor
    
    Args:
        co_ppm: Carbon monoxide in ppm
        co2_ppm: Carbon dioxide in ppm
        ch4_ppm: Methane in ppm
        
    Returns:
        Dictionary with aqi, category, color, and dominant_pollutant
    """
    aqi_values = {}
    
    # CO (Carbon Monoxide) thresholds in ppm
    # EPA standards: 9 ppm (8-hour), 35 ppm (1-hour)
    # Indoor safety: < 9 ppm good, > 35 ppm dangerous
    if co_ppm is not None:
        if co_ppm <= 1:
            aqi_values['co'] = 25  # Excellent
        elif co_ppm <= 4:
            aqi_values['co'] = 50  # Good
        elif co_ppm <= 9:
            aqi_values['co'] = 75  # Moderate
        elif co_ppm <= 15:
            aqi_values['co'] = 100  # Moderate-Unhealthy
        elif co_ppm <= 25:
            aqi_values['co'] = 125  # Unhealthy for Sensitive
        elif co_ppm <= 35:
            aqi_values['co'] = 150  # Unhealthy
        elif co_ppm <= 50:
            aqi_values['co'] = 200  # Unhealthy
        elif co_ppm <= 100:
            aqi_values['co'] = 300  # Very Unhealthy
        else:
            aqi_values['co'] = 400  # Hazardous
    
    # CO2 (Carbon Dioxide) thresholds in ppm
    # Outdoor air: ~400 ppm
    # Indoor standards: < 1000 ppm good, > 2000 ppm poor
    if co2_ppm is not None:
        if co2_ppm <= 400:
            aqi_values['co2'] = 25  # Excellent (outdoor level)
        elif co2_ppm <= 600:
            aqi_values['co2'] = 50  # Good
        elif co2_ppm <= 1000:
            aqi_values['co2'] = 75  # Acceptable
        elif co2_ppm <= 1500:
            aqi_values['co2'] = 100  # Moderate
        elif co2_ppm <= 2000:
            aqi_values['co2'] = 125  # Unhealthy for Sensitive
        elif co2_ppm <= 2500:
            aqi_values['co2'] = 150  # Unhealthy
        elif co2_ppm <= 5000:
            aqi_values['co2'] = 200  # Very Unhealthy
        else:
            aqi_values['co2'] = 300  # Hazardous
    
    # CH4 (Methane) thresholds in ppm
    # Outdoor air: ~2 ppm
    # Safety threshold: < 5000 ppm (0.5% LEL)
    if ch4_ppm is not None:
        if ch4_ppm <= 2:
            aqi_values['ch4'] = 25  # Excellent (outdoor level)
        elif ch4_ppm <= 10:
            aqi_values['ch4'] = 50  # Good
        elif ch4_ppm <= 50:
            aqi_values['ch4'] = 75  # Acceptable
        elif ch4_ppm <= 100:
            aqi_values['ch4'] = 100  # Moderate
        elif ch4_ppm <= 500:
            aqi_values['ch4'] = 125  # Unhealthy for Sensitive
        elif ch4_ppm <= 1000:
            aqi_values['ch4'] = 150  # Unhealthy
        elif ch4_ppm <= 5000:
            aqi_values['ch4'] = 200  # Very Unhealthy
        else:
            aqi_values['ch4'] = 300  # Hazardous
    
    # If no valid sensor data, return default
    if not aqi_values:
        return {
            'aqi': None,
            'category': None,
            'color': None,
            'dominant_pollutant': None
        }
    
    # Find the worst (maximum) AQI value
    dominant_pollutant_key = max(aqi_values, key=aqi_values.get)
    max_aqi = aqi_values[dominant_pollutant_key]
    
    # Map pollutant key to readable name
    pollutant_names = {
        'co': 'CO',
        'co2': 'CO₂',
        'ch4': 'CH₄'
    }
    
    # Get category info
    category_info = get_aqi_category(max_aqi)
    
    return {
        'aqi': max_aqi,
        'category': category_info.get('category'),
        'color': category_info.get('color'),
        'dominant_pollutant': pollutant_names.get(dominant_pollutant_key)
    }



def get_aqi_category(aqi: int) -> dict:
    """
    Get AQI category, color, and health advice based on AQI value
    
    Args:
        aqi: AQI value (0-500)
        
    Returns:
        Dictionary with category, color, and health_advice
    """
    # Handle None or invalid values
    if aqi is None or not isinstance(aqi, (int, float)):
        return {
            'category': 'Unknown',
            'color': '#808080',
            'health_advice': 'Unable to determine air quality.'
        }
    
    # Convert to int if float
    aqi = int(aqi)
    
    if aqi <= 50:
        return {
            'category': 'Good',
            'color': '#00E400',
            'health_advice': 'Air quality is satisfactory, and air pollution poses little or no risk.'
        }
    elif aqi <= 100:
        return {
            'category': 'Moderate',
            'color': '#FFFF00',
            'health_advice': 'Air quality is acceptable. However, there may be a risk for some people, particularly those who are unusually sensitive to air pollution.'
        }
    elif aqi <= 150:
        return {
            'category': 'Unhealthy for Sensitive Groups',
            'color': '#FF7E00',
            'health_advice': 'Members of sensitive groups may experience health effects. The general public is less likely to be affected.'
        }
    elif aqi <= 200:
        return {
            'category': 'Unhealthy',
            'color': '#FF0000',
            'health_advice': 'Some members of the general public may experience health effects; members of sensitive groups may experience more serious health effects.'
        }
    elif aqi <= 300:
        return {
            'category': 'Very Unhealthy',
            'color': '#8F3F97',
            'health_advice': 'Health alert: The risk of health effects is increased for everyone.'
        }
    else:
        return {
            'category': 'Hazardous',
            'color': '#7E0023',
            'health_advice': 'Health warning of emergency conditions: everyone is more likely to be affected.'
        }

