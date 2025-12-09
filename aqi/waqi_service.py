"""
WAQI (World Air Quality Index) API integration service
"""
import requests
import time
import threading
import logging
from typing import Dict, List, Optional, Any
from django.conf import settings
from core.utils import calculate_epa_aqi, get_aqi_category, reverse_geocode

logger = logging.getLogger(__name__)

# WAQI API Configuration
WAQI_TOKEN = '61d498576ee7f9598f8bf5426a4475fc0ff2a1e2'
WAQI_BASE_URL = 'https://api.waqi.info'


class WAQIService:
    """
    Service for fetching Air Quality data from WAQI API
    """
    
    # Request throttling - class-level lock and last request time
    _request_lock = threading.Lock()
    _last_request_time = 0
    _min_request_interval = 1.0  # Minimum 1.0s between requests
    _max_request_interval = 2.0  # Maximum interval after rate limiting
    
    # Default headers for all requests
    DEFAULT_HEADERS = {
        'User-Agent': 'BreatheEasy-AQI-App/1.0',
        'Accept': 'application/json',
    }
    
    # Global bounding boxes for major regions (15-20 boxes for detailed coverage)
    GLOBAL_BOUNDING_BOXES = [
        # North America
        {'min_lat': 25.0, 'min_lon': -125.0, 'max_lat': 49.0, 'max_lon': -66.0, 'region': 'North America'},  # USA
        {'min_lat': 42.0, 'min_lon': -141.0, 'max_lat': 70.0, 'max_lon': -52.0, 'region': 'North America'},  # Canada
        {'min_lat': 14.0, 'min_lon': -118.0, 'max_lat': 32.0, 'max_lon': -86.0, 'region': 'North America'},  # Mexico & Central America
        
        # South America
        {'min_lat': -5.0, 'min_lon': -82.0, 'max_lat': 12.0, 'max_lon': -34.0, 'region': 'South America'},  # North South America
        {'min_lat': -56.0, 'min_lon': -81.0, 'max_lat': -5.0, 'max_lon': -34.0, 'region': 'South America'},  # South South America
        
        # Europe
        {'min_lat': 35.0, 'min_lon': -10.0, 'max_lat': 55.0, 'max_lon': 25.0, 'region': 'Europe'},  # Western Europe
        {'min_lat': 40.0, 'min_lon': 25.0, 'max_lat': 55.0, 'max_lon': 40.0, 'region': 'Europe'},  # Eastern Europe
        {'min_lat': 55.0, 'min_lon': 5.0, 'max_lat': 71.0, 'max_lon': 32.0, 'region': 'Europe'},  # Northern Europe
        {'min_lat': 36.0, 'min_lon': -5.0, 'max_lat': 47.0, 'max_lon': 25.0, 'region': 'Europe'},  # Southern Europe
        
        # Asia
        {'min_lat': 20.0, 'min_lon': 100.0, 'max_lat': 50.0, 'max_lon': 135.0, 'region': 'Asia'},  # East Asia
        {'min_lat': 5.0, 'min_lon': 65.0, 'max_lat': 37.0, 'max_lon': 100.0, 'region': 'Asia'},  # South Asia
        {'min_lat': -11.0, 'min_lon': 95.0, 'max_lat': 29.0, 'max_lon': 141.0, 'region': 'Asia'},  # Southeast Asia
        {'min_lat': 35.0, 'min_lon': 40.0, 'max_lat': 55.0, 'max_lon': 100.0, 'region': 'Asia'},  # Central Asia
        {'min_lat': 12.0, 'min_lon': 26.0, 'max_lat': 42.0, 'max_lon': 65.0, 'region': 'Asia'},  # Middle East
        
        # Africa
        {'min_lat': 10.0, 'min_lon': -20.0, 'max_lat': 38.0, 'max_lon': 55.0, 'region': 'Africa'},  # North Africa
        {'min_lat': -35.0, 'min_lon': 8.0, 'max_lat': 10.0, 'max_lon': 52.0, 'region': 'Africa'},  # Sub-Saharan Africa
        
        # Oceania
        {'min_lat': -45.0, 'min_lon': 110.0, 'max_lat': -10.0, 'max_lon': 155.0, 'region': 'Oceania'},  # Australia & New Zealand
        {'min_lat': -20.0, 'min_lon': 155.0, 'max_lat': 10.0, 'max_lon': 180.0, 'region': 'Oceania'},  # Pacific Islands (East)
        {'min_lat': -20.0, 'min_lon': -180.0, 'max_lat': 10.0, 'max_lon': -150.0, 'region': 'Oceania'},  # Pacific Islands (West)
    ]
    
    def __init__(self):
        """Initialize WAQI service"""
        self.timeout = getattr(settings, 'WAQI_TIMEOUT', 30)
        self.min_interval = getattr(settings, 'WAQI_MIN_INTERVAL', 1.0)
        self.max_retries = getattr(settings, 'WAQI_MAX_RETRIES', 3)
        
        if hasattr(settings, 'WAQI_MIN_INTERVAL'):
            self._min_request_interval = self.min_interval
    
    def _throttle_request(self):
        """
        Throttle requests to avoid rate limiting
        Ensures minimum interval between API requests
        """
        with self._request_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            
            if time_since_last < self._min_request_interval:
                sleep_time = self._min_request_interval - time_since_last
                logger.debug(f"Throttling WAQI request: waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)
            
            self._last_request_time = time.time()
    
    def fetch_stations_by_bounds(
        self, 
        min_lat: float, 
        min_lon: float, 
        max_lat: float, 
        max_lon: float
    ) -> List[Dict[str, Any]]:
        """
        Fetch WAQI stations within a bounding box
        
        Args:
            min_lat: Minimum latitude
            min_lon: Minimum longitude
            max_lat: Maximum latitude
            max_lon: Maximum longitude
            
        Returns:
            List of station dictionaries with lat, lon, and other metadata
        """
        self._throttle_request()
        
        url = f"{WAQI_BASE_URL}/map/bounds/"
        params = {
            'latlng': f"{min_lat},{min_lon},{max_lat},{max_lon}",
            'token': WAQI_TOKEN
        }
        
        try:
            response = requests.get(
                url, 
                params=params, 
                headers=self.DEFAULT_HEADERS,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ok' and isinstance(data.get('data'), list):
                stations = data['data']
                logger.debug(f"Fetched {len(stations)} stations from bounding box")
                return stations
            else:
                logger.warning(f"WAQI API returned non-ok status: {data.get('status')}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching WAQI stations: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching WAQI stations: {e}", exc_info=True)
            return []
    
    def fetch_aqi_for_station(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        Fetch AQI data for a specific station by coordinates
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Dictionary with AQI data or None if error
        """
        self._throttle_request()
        
        url = f"{WAQI_BASE_URL}/feed/geo:{lat};{lon}/"
        params = {'token': WAQI_TOKEN}
        
        try:
            response = requests.get(
                url,
                params=params,
                headers=self.DEFAULT_HEADERS,
                timeout=self.timeout
            )
            response.raise_for_status()
            json_data = response.json()
            
            if json_data.get('status') == 'ok':
                return json_data.get('data')
            else:
                logger.debug(f"WAQI API returned non-ok status for station ({lat}, {lon}): {json_data.get('status')}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"Error fetching WAQI AQI for station ({lat}, {lon}): {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error fetching WAQI AQI for station ({lat}, {lon}): {e}")
            return None
    
    def _determine_region_from_coords(self, lat: float, lon: float) -> str:
        """
        Determine region from coordinates by checking which bounding box contains them
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            Region name
        """
        for bbox in self.GLOBAL_BOUNDING_BOXES:
            if (bbox['min_lat'] <= lat <= bbox['max_lat'] and 
                bbox['min_lon'] <= lon <= bbox['max_lon']):
                return bbox['region']
        
        # Default fallback
        if -90 <= lat < -35:
            return 'Antarctica'
        return 'Unknown'
    
    def _extract_country_from_city_name(self, city_name: str) -> str:
        """
        Try to extract country from city name (e.g., "Beijing, China")
        
        Args:
            city_name: City name string
            
        Returns:
            Country name or "Unknown"
        """
        if ',' in city_name:
            parts = city_name.split(',')
            if len(parts) > 1:
                return parts[-1].strip()
        return 'Unknown'
    
    def build_worst_aqi_rankings(self, top_n: int = 30, max_time_seconds: int = 60) -> List[Dict[str, Any]]:
        """
        Build ranking of worst AQI cities globally
        
        Args:
            top_n: Number of top cities to return (default: 30)
            max_time_seconds: Maximum time to spend building rankings (default: 60)
            
        Returns:
            List of city ranking dictionaries matching CityRankingSerializer format
        """
        start_time = time.time()
        
        logger.info(f"Building WAQI city rankings (top {top_n}, max {max_time_seconds}s)")
        
        city_aqi_map = {}  # For deduplication: city_name -> worst AQI data
        max_stations_per_box = 30  # Limit stations per bounding box to speed up
        stations_processed = 0
        max_total_stations = 200  # Total limit across all boxes
        
        # Iterate through all bounding boxes
        for bbox_idx, bbox in enumerate(self.GLOBAL_BOUNDING_BOXES):
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > max_time_seconds:
                logger.warning(f"Timeout reached ({elapsed:.1f}s), stopping early with {len(city_aqi_map)} cities")
                break
            
            # Early exit if we have enough high-AQI cities
            if len(city_aqi_map) >= top_n * 2:
                # Check if we have enough high-AQI cities (AQI > 100)
                high_aqi_count = sum(1 for obs in city_aqi_map.values() if obs.get('aqi', 0) > 100)
                if high_aqi_count >= top_n:
                    logger.info(f"Found {high_aqi_count} high-AQI cities, stopping early")
                    break
            
            logger.debug(f"Processing bounding box {bbox_idx + 1}/{len(self.GLOBAL_BOUNDING_BOXES)}: {bbox.get('region', 'Unknown')}")
            
            # Fetch stations for this bounding box
            stations = self.fetch_stations_by_bounds(
                bbox['min_lat'],
                bbox['min_lon'],
                bbox['max_lat'],
                bbox['max_lon']
            )
            
            if not stations:
                continue
            
            # Limit stations per bounding box
            stations = stations[:max_stations_per_box]
            
            # Fetch AQI data for each station
            for station in stations:
                # Check total stations limit
                if stations_processed >= max_total_stations:
                    logger.info(f"Reached max stations limit ({max_total_stations}), stopping")
                    break
                
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > max_time_seconds:
                    break
                
                station_lat = station.get('lat')
                station_lon = station.get('lon')
                
                if station_lat is None or station_lon is None:
                    continue
                
                stations_processed += 1
                
                # Fetch AQI data for this station
                aqi_data = self.fetch_aqi_for_station(station_lat, station_lon)
                
                if not aqi_data:
                    continue
                
                # Extract AQI value
                aqi_value = aqi_data.get('aqi')
                
                # Filter invalid data
                if aqi_value is None or not isinstance(aqi_value, (int, float)) or aqi_value <= 0:
                    continue
                
                # Extract city name
                city_info = aqi_data.get('city', {})
                city_name = city_info.get('name', 'Unknown')
                
                # Skip reverse geocoding for speed - use what WAQI provides
                if city_name == 'Unknown' or not city_name:
                    continue  # Skip stations without city names
                
                # Extract coordinates
                geo = city_info.get('geo', [])
                if not geo or len(geo) < 2:
                    geo = [station_lat, station_lon]
                
                lat = geo[0] if isinstance(geo, list) else station_lat
                lon = geo[1] if isinstance(geo, list) else station_lon
                
                # Extract pollutant data from iaqi
                iaqi = aqi_data.get('iaqi', {})
                pm25_data = iaqi.get('pm25', {})
                pm10_data = iaqi.get('pm10', {})
                
                pm25 = pm25_data.get('v') if isinstance(pm25_data, dict) else None
                pm10 = pm10_data.get('v') if isinstance(pm10_data, dict) else None
                
                # Extract time
                time_info = aqi_data.get('time', {})
                last_updated = time_info.get('s', '') if isinstance(time_info, dict) else ''
                
                # Determine country and region (skip slow reverse geocoding)
                country = self._extract_country_from_city_name(city_name)
                if country == 'Unknown':
                    country = 'Unknown'  # Don't reverse geocode - too slow
                
                region = self._determine_region_from_coords(lat, lon)
                
                # Calculate EPA AQI for pollutants if available
                aqi_pm25 = None
                aqi_pm10 = None
                if pm25 is not None:
                    aqi_pm25 = calculate_epa_aqi('pm25', pm25)
                if pm10 is not None:
                    aqi_pm10 = calculate_epa_aqi('pm10', pm10)
                
                # Determine dominant pollutant
                dominant_pollutant = 'pm2_5'
                if pm25 and pm10:
                    # Use the one with higher AQI
                    if aqi_pm10 and aqi_pm25:
                        dominant_pollutant = 'pm10' if aqi_pm10 > aqi_pm25 else 'pm2_5'
                    else:
                        dominant_pollutant = 'pm10' if pm10 > pm25 else 'pm2_5'
                elif pm10:
                    dominant_pollutant = 'pm10'
                
                # Get AQI category
                aqi_info = get_aqi_category(int(aqi_value))
                
                # Create observation
                observation = {
                    'city': city_name,
                    'country': country,
                    'aqi': int(round(aqi_value)),
                    'category': aqi_info['category'],
                    'dominantPollutant': dominant_pollutant,
                    'lastUpdated': last_updated,
                    'region': region,
                    'pm25': round(pm25, 2) if pm25 is not None else None,
                    'pm10': round(pm10, 2) if pm10 is not None else None,
                    'aqi_pm25': aqi_pm25,
                    'aqi_pm10': aqi_pm10,
                    'trend': [{'time': last_updated, 'aqi': int(round(aqi_value))}],
                    'lat': lat,
                    'lon': lon,
                }
                
                # Deduplicate by city name - keep worst AQI per city
                city_key = f"{city_name}_{country}".lower()
                if city_key not in city_aqi_map:
                    city_aqi_map[city_key] = observation
                else:
                    # Keep the one with higher (worse) AQI
                    if observation['aqi'] > city_aqi_map[city_key]['aqi']:
                        city_aqi_map[city_key] = observation
            
            if stations_processed >= max_total_stations:
                break
        
        # Convert map to list and sort by AQI descending
        all_observations = list(city_aqi_map.values())
        all_observations.sort(key=lambda x: x['aqi'], reverse=True)
        
        # Assign ranks and return top N
        for i, obs in enumerate(all_observations[:top_n], 1):
            obs['rank'] = i
        
        elapsed = time.time() - start_time
        logger.info(f"Built rankings with {len(all_observations[:top_n])} cities in {elapsed:.1f}s (processed {stations_processed} stations)")
        return all_observations[:top_n]

