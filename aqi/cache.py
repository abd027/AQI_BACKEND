"""
Caching utilities for AQI data
"""
from django.core.cache import cache
from typing import Optional, Dict, Any, List
from django.conf import settings
import hashlib
import json


def generate_cache_key(
    latitude: float,
    longitude: float,
    data_type: str = 'current',
    hours: Optional[int] = None,
    days: Optional[int] = None
) -> str:
    """
    Generate cache key for AQI data request
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        data_type: Type of data ('current', 'hourly', 'daily', 'enhanced')
        hours: Number of hours (for hourly data)
        days: Number of days (for daily data)
        
    Returns:
        Cache key string
    """
    # Round coordinates to 4 decimal places for cache key (approx 11m precision)
    lat_rounded = round(latitude, 4)
    lon_rounded = round(longitude, 4)
    
    key_parts = [
        'aqi',
        data_type,
        str(lat_rounded),
        str(lon_rounded),
    ]
    
    if hours:
        key_parts.append(f'h{hours}')
    if days:
        key_parts.append(f'd{days}')
    
    cache_key = ':'.join(key_parts)
    
    # Hash if key is too long (Redis key length limit)
    if len(cache_key) > 250:
        cache_key = 'aqi:' + hashlib.md5(cache_key.encode()).hexdigest()
    
    return cache_key


def get_cached_aqi(
    latitude: float,
    longitude: float,
    data_type: str = 'current',
    hours: Optional[int] = None,
    days: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Get cached AQI data
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        data_type: Type of data ('current', 'hourly', 'daily', 'enhanced')
        hours: Number of hours (for hourly data)
        days: Number of days (for daily data)
        
    Returns:
        Cached AQI data or None if not found
    """
    cache_key = generate_cache_key(latitude, longitude, data_type, hours, days)
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data
    
    return None


def set_cached_aqi(
    latitude: float,
    longitude: float,
    data: Dict[str, Any],
    data_type: str = 'current',
    hours: Optional[int] = None,
    days: Optional[int] = None,
    ttl: Optional[int] = None
) -> bool:
    """
    Cache AQI data
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        data: AQI data to cache
        data_type: Type of data ('current', 'hourly', 'daily', 'enhanced')
        hours: Number of hours (for hourly data)
        days: Number of days (for daily data)
        ttl: Time to live in seconds (defaults to AQI_CACHE_TTL from settings)
        
    Returns:
        True if cached successfully
    """
    cache_key = generate_cache_key(latitude, longitude, data_type, hours, days)
    
    if ttl is None:
        ttl = getattr(settings, 'AQI_CACHE_TTL', 300)  # Default 5 minutes
    
    try:
        cache.set(cache_key, data, timeout=ttl)
        return True
    except Exception as e:
        print(f"Error caching AQI data: {e}")
        return False


def clear_aqi_cache(
    latitude: float,
    longitude: float,
    data_type: Optional[str] = None
) -> bool:
    """
    Clear cached AQI data for a location
    
    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate
        data_type: Type of data to clear (None clears all types)
        
    Returns:
        True if cleared successfully
    """
    if data_type:
        cache_key = generate_cache_key(latitude, longitude, data_type)
        cache.delete(cache_key)
    else:
        # Clear all types
        for dt in ['current', 'hourly', 'daily', 'enhanced']:
            cache_key = generate_cache_key(latitude, longitude, dt)
            cache.delete(cache_key)
    
    return True


def get_cached_city_rankings() -> Optional[List[Dict[str, Any]]]:
    """
    Get cached city rankings data
    
    Returns:
        Cached city rankings list or None if not found
    """
    cache_key = 'waqi:city_rankings'
    cached_data = cache.get(cache_key)
    
    if cached_data:
        return cached_data
    
    return None


def set_cached_city_rankings(
    rankings: List[Dict[str, Any]],
    ttl: Optional[int] = None
) -> bool:
    """
    Cache city rankings data
    
    Args:
        rankings: List of city ranking dictionaries
        ttl: Time to live in seconds (defaults to WAQI_CITY_RANKINGS_CACHE_TTL from settings)
        
    Returns:
        True if cached successfully
    """
    cache_key = 'waqi:city_rankings'
    
    if ttl is None:
        ttl = getattr(settings, 'WAQI_CITY_RANKINGS_CACHE_TTL', 900)  # Default 15 minutes
    
    try:
        cache.set(cache_key, rankings, timeout=ttl)
        return True
    except Exception as e:
        print(f"Error caching city rankings: {e}")
        return False
