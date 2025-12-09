"""
Open-Meteo Air Quality API integration service
"""
import requests
import time
import threading
import logging
import queue
from typing import Dict, List, Optional, Any
from django.conf import settings
from core.utils import calculate_epa_aqi, get_aqi_category, reverse_geocode
from .cache import get_cached_aqi, set_cached_aqi
try:
    from .rag import AQIRAGSystem
except ImportError:
    AQIRAGSystem = None

# Configure logging
logger = logging.getLogger(__name__)


class OpenMeteoAQIService:
    """
    Service for fetching Air Quality and Weather data from Open-Meteo API
    """
    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
    WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
    
    # Supported pollutants
    POLLUTANTS = [
        'pm10',
        'pm2_5',
        'carbon_monoxide',
        'nitrogen_dioxide',
        'sulphur_dioxide',
        'ozone',
        'dust',
        'uv_index',
        'alder_pollen',
        'birch_pollen',
        'grass_pollen',
        'mugwort_pollen',
        'olive_pollen',
        'ragweed_pollen',
    ]
    
    # Request throttling - class-level lock and last request time
    _request_lock = threading.Lock()
    _last_request_time = 0
    _min_request_interval = 1.0  # Minimum 1.0s between requests to avoid rate limiting (increased from 0.5s)
    _max_request_interval = 2.0  # Maximum interval after rate limiting
    _request_queue = queue.Queue()  # Queue to serialize API calls
    
    # Default headers for all requests
    DEFAULT_HEADERS = {
        'User-Agent': 'BreatheEasy-AQI-App/1.0',
        'Accept': 'application/json',
    }
    
    def __init__(self):
        # Get configurable settings with defaults
        self.timeout = getattr(settings, 'OPEN_METEO_TIMEOUT', 30)
        self.min_interval = getattr(settings, 'OPEN_METEO_MIN_INTERVAL', 1.0)
        self.max_retries = getattr(settings, 'OPEN_METEO_MAX_RETRIES', 3)
        
        # Use configured interval if available
        if hasattr(settings, 'OPEN_METEO_MIN_INTERVAL'):
            self._min_request_interval = self.min_interval
    
    def _throttle_request(self):
        """
        Throttle requests to avoid rate limiting
        Ensures minimum interval between API requests with adaptive throttling
        """
        with self._request_lock:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time
            
            if time_since_last < self._min_request_interval:
                sleep_time = self._min_request_interval - time_since_last
                logger.debug(f"Throttling request: waiting {sleep_time:.2f}s (interval: {self._min_request_interval:.2f}s)")
                time.sleep(sleep_time)
            
            self._last_request_time = time.time()
    
    def _adjust_throttle_interval(self, increase: bool = False):
        """
        Adjust throttle interval adaptively based on rate limiting
        Increases after rate limits, gradually decreases on success
        """
        with self._request_lock:
            if increase:
                # Increase interval after rate limit (up to max)
                self._min_request_interval = min(self._min_request_interval * 1.5, self._max_request_interval)
                logger.warning(f"Increased throttle interval to {self._min_request_interval:.2f}s due to rate limiting")
            else:
                # Gradually decrease interval on success (but not below initial)
                if self._min_request_interval > self.min_interval:
                    self._min_request_interval = max(self._min_request_interval * 0.95, self.min_interval)
                    logger.debug(f"Decreased throttle interval to {self._min_request_interval:.2f}s after successful request")
    
    def _make_request(self, params: Dict[str, Any], retries: Optional[int] = None) -> Optional[Dict]:
        """
        Make HTTP request to Open-Meteo Air Quality API with retry logic for rate limiting
        
        Args:
            params: Query parameters for the API
            retries: Number of retry attempts (default: from settings or 3)
            
        Returns:
            JSON response or None if error
        """
        if retries is None:
            retries = self.max_retries
        
        # Throttle request to avoid rate limiting
        self._throttle_request()
        
        # Sanitize params for logging (remove sensitive data if any)
        log_params = {k: v for k, v in params.items() if k not in ['api_key', 'key']}
        
        for attempt in range(retries):
            try:
                logger.debug(f"Making Open-Meteo AQI API request (attempt {attempt + 1}/{retries}): {log_params}")
                
                response = requests.get(
                    self.BASE_URL,
                    params=params,
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout
                )
                
                # Log response status for debugging
                if response.status_code != 200:
                    logger.warning(f"Open-Meteo AQI API returned status {response.status_code}")
                    # Try to get error details from response
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error') or error_data.get('reason', 'Unknown error')
                        logger.error(f"API Error: {error_msg}")
                    except:
                        logger.error(f"API returned non-200 status: {response.status_code}")
                
                # Handle rate limiting (429) with exponential backoff
                if response.status_code == 429:
                    if attempt < retries - 1:
                        # Exponential backoff: 2s, 5s, 10s
                        wait_time = 2 * (2 ** attempt) + (attempt * 1)
                        logger.warning(f"Rate limited (429). Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        # Increase throttle interval after rate limit
                        self._adjust_throttle_interval(increase=True)
                        continue
                    else:
                        logger.error(f"Rate limited (429). Max retries ({retries}) reached.")
                        return None
                
                # Handle 400 Bad Request (likely invalid parameters)
                if response.status_code == 400:
                    logger.error(f"Bad Request (400) - Invalid parameters")
                    try:
                        error_data = response.json()
                        logger.error(f"API Error details: {error_data}")
                    except:
                        pass
                    return None
                
                # Handle other HTTP errors
                if response.status_code >= 500:
                    if attempt < retries - 1:
                        wait_time = (2 ** attempt)
                        logger.warning(f"Server error ({response.status_code}). Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Server error ({response.status_code}) after {retries} attempts")
                        return None
                
                response.raise_for_status()
                
                # Validate response structure
                try:
                    # Check response content length
                    content_length = len(response.content)
                    if content_length == 0:
                        logger.warning("Received empty response from Open-Meteo AQI API")
                        return None
                    
                    data = response.json()
                    
                    # Open-Meteo API should return a dict, but handle edge cases
                    if data is None:
                        logger.warning("Received null response from Open-Meteo AQI API")
                        return None
                    
                    # For batch requests, the API might return a dict with arrays
                    # For single requests, it should be a dict
                    # Handle empty list responses (might indicate rate limiting or error)
                    if isinstance(data, list):
                        if len(data) == 0:
                            logger.warning("Received empty list response from Open-Meteo AQI API (possibly rate limited)")
                            return None
                        else:
                            logger.warning(f"Received list response instead of dict from Open-Meteo AQI API. Length: {len(data)}")
                            # Convert list to dict if possible, otherwise return None
                            return None
                    
                    # Log warning if unexpected format but don't fail for other types
                    if not isinstance(data, dict):
                        logger.warning(f"Unexpected response format from Open-Meteo AQI API: expected dict, got {type(data)}. Response preview: {str(data)[:200]}")
                        return None
                    
                    # Adjust throttle interval on success (gradually decrease)
                    self._adjust_throttle_interval(increase=False)
                    
                    logger.debug(f"Successfully received response from Open-Meteo AQI API (size: {content_length} bytes)")
                    return data
                except ValueError as e:
                    logger.error(f"Failed to parse JSON response: {e}. Response content: {response.text[:200]}")
                    return None
                    
            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    wait_time = (2 ** attempt)
                    logger.warning(f"Request timeout. Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Request timeout after {retries} attempts")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching from Open-Meteo AQI API: {e}")
                if attempt < retries - 1:
                    wait_time = (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                return None
        
        return None
    
    def _make_weather_request(self, params: Dict[str, Any], retries: Optional[int] = None) -> Optional[Dict]:
        """
        Make HTTP request to Open-Meteo Weather API with retry logic for rate limiting
        Uses same throttling mechanism as AQI API
        
        Args:
            params: Query parameters for the API
            retries: Number of retry attempts (default: from settings or 3)
            
        Returns:
            JSON response or None if error
        """
        if retries is None:
            retries = self.max_retries
        
        # Throttle request to avoid rate limiting (shared with AQI API)
        self._throttle_request()
        
        # Sanitize params for logging
        log_params = {k: v for k, v in params.items() if k not in ['api_key', 'key']}
        
        for attempt in range(retries):
            try:
                logger.debug(f"Making Open-Meteo Weather API request (attempt {attempt + 1}/{retries}): {log_params}")
                
                response = requests.get(
                    self.WEATHER_URL,
                    params=params,
                    headers=self.DEFAULT_HEADERS,
                    timeout=self.timeout
                )
                
                # Log response status for debugging
                if response.status_code != 200:
                    logger.warning(f"Open-Meteo Weather API returned status {response.status_code}")
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('error') or error_data.get('reason', 'Unknown error')
                        logger.error(f"API Error: {error_msg}")
                    except:
                        logger.error(f"API returned non-200 status: {response.status_code}")
                
                # Handle rate limiting (429) with exponential backoff
                if response.status_code == 429:
                    if attempt < retries - 1:
                        wait_time = 2 * (2 ** attempt) + (attempt * 1)
                        logger.warning(f"Rate limited (429). Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        self._adjust_throttle_interval(increase=True)
                        continue
                    else:
                        logger.error(f"Rate limited (429). Max retries ({retries}) reached.")
                        return None
                
                # Handle 400 Bad Request
                if response.status_code == 400:
                    logger.error(f"Bad Request (400) - Invalid parameters")
                    try:
                        error_data = response.json()
                        logger.error(f"API Error details: {error_data}")
                    except:
                        pass
                    return None
                
                # Handle other HTTP errors
                if response.status_code >= 500:
                    if attempt < retries - 1:
                        wait_time = (2 ** attempt)
                        logger.warning(f"Server error ({response.status_code}). Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{retries})")
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Server error ({response.status_code}) after {retries} attempts")
                        return None
                
                response.raise_for_status()
                
                # Validate response structure
                try:
                    data = response.json()
                    if not isinstance(data, dict):
                        logger.error(f"Invalid response format: expected dict, got {type(data)}")
                        return None
                    
                    # Adjust throttle interval on success
                    self._adjust_throttle_interval(increase=False)
                    
                    logger.debug(f"Successfully received response from Open-Meteo Weather API")
                    return data
                except ValueError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    return None
                    
            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    wait_time = (2 ** attempt)
                    logger.warning(f"Request timeout. Retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Request timeout after {retries} attempts")
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching from Open-Meteo Weather API: {e}")
                if attempt < retries - 1:
                    wait_time = (2 ** attempt)
                    time.sleep(wait_time)
                    continue
                return None
        
        return None
    
    def fetch_weather_data(
        self,
        latitude: float,
        longitude: float,
        timezone: str = "auto"
    ) -> Optional[Dict]:
        """
        Fetch current weather data from Open-Meteo Weather API
        Uses throttled request method to respect rate limits
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            timezone: Timezone (default: "auto")
            
        Returns:
            Weather data dictionary with temperature, humidity, wind_speed
        """
        # Validate coordinates
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            logger.error(f"Invalid coordinates: lat={latitude}, lon={longitude}")
            return None
        
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m',
            'timezone': timezone,
        }
        
        data = self._make_weather_request(params)
        if not data:
            logger.warning(f"Failed to fetch weather data for lat={latitude}, lon={longitude}")
            return None
        
        # Validate response structure
        current = data.get('current', {})
        if not isinstance(current, dict):
            logger.error(f"Invalid weather response structure: current is not a dict")
            return None
        
        return {
            'temperature': current.get('temperature_2m'),
            'humidity': current.get('relative_humidity_2m'),
            'wind': current.get('wind_speed_10m'),
        }

    
    def fetch_current_aqi(
        self,
        latitude: float,
        longitude: float,
        timezone: str = "auto"
    ) -> Optional[Dict]:
        """
        Fetch current air quality data
        
        According to Open-Meteo API docs:
        - Use 'current' parameter for current conditions (15-minutely data)
        - Include european_aqi and us_aqi for AQI indices
        - Include all pollutants for comprehensive data
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            timezone: Timezone (default: "auto")
            
        Returns:
            Formatted AQI data dictionary
        """
        # Check cache first to avoid unnecessary API calls
        cached_data = get_cached_aqi(latitude, longitude, 'current')
        if cached_data:
            return cached_data
        
        # Build current parameters according to Open-Meteo API documentation
        # Include pollutants and main AQI indices (sub-indices can be requested separately if needed)
        current_params = ','.join([
            'pm10',
            'pm2_5',
            'carbon_monoxide',
            'nitrogen_dioxide',
            'sulphur_dioxide',
            'ozone',
            'dust',
            'uv_index',
            'european_aqi',
            'us_aqi',
        ])
        
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'current': current_params,
            'timezone': timezone,
        }
        
        data = self._make_request(params)
        if not data:
            return None
        
        formatted_data = self._format_current_response(data, latitude, longitude)
        
        # Cache the response
        if formatted_data:
            set_cached_aqi(latitude, longitude, formatted_data, 'current')
        
        return formatted_data
    
    def fetch_batch_current_aqi(
        self,
        locations: List[Dict[str, float]],
        timezone: str = "auto"
    ) -> Optional[List[Dict]]:
        """
        Fetch current air quality data for multiple locations in a single batch
        
        According to Open-Meteo API docs:
        - When multiple coordinates are provided (comma-separated), the API returns
          a single response object with arrays for latitude, longitude, and current data
        - Each index in the arrays corresponds to one location
        - API may have limitations on batch size, so we split into chunks if needed
        
        Args:
            locations: List of dicts with 'lat' and 'lon' keys
            timezone: Timezone (default: "auto")
            
        Returns:
            List of formatted AQI data dictionaries
        """
        if not locations:
            return []

        # Open-Meteo API may have limitations on batch size
        # Split into chunks of 20 to avoid rate limiting and ensure reliability
        BATCH_CHUNK_SIZE = 20
        all_results = []
        
        for chunk_start in range(0, len(locations), BATCH_CHUNK_SIZE):
            chunk_end = min(chunk_start + BATCH_CHUNK_SIZE, len(locations))
            chunk_locations = locations[chunk_start:chunk_end]
            
            try:
                # Prepare comma-separated lists of coordinates for this chunk
                latitudes = [str(loc['lat']) for loc in chunk_locations]
                longitudes = [str(loc['lon']) for loc in chunk_locations]
                
                # Use same current parameters as single location fetch
                # According to Open-Meteo docs, these are the available current parameters
                current_params = ','.join([
                    'pm10',
                    'pm2_5',
                    'carbon_monoxide',
                    'nitrogen_dioxide',
                    'sulphur_dioxide',
                    'ozone',
                    'dust',
                    'uv_index',
                    'european_aqi',
                    'us_aqi',
                ])
                
                params = {
                    'latitude': ','.join(latitudes),
                    'longitude': ','.join(longitudes),
                    'current': current_params,
                    'timezone': timezone,
                }
                
                logger.debug(f"Fetching batch AQI for chunk {chunk_start}-{chunk_end} ({len(chunk_locations)} locations)")
                data = self._make_request(params)
                
                if not data:
                    logger.warning(f"Batch AQI request returned no data for chunk {chunk_start}-{chunk_end}")
                    # Add None placeholders to maintain index alignment
                    all_results.extend([None] * len(chunk_locations))
                    continue
                
                # Check if we got an error response
                if isinstance(data, dict) and data.get('error'):
                    error_reason = data.get('reason', data.get('detail', 'Unknown error'))
                    logger.error(f"Batch AQI request error for chunk {chunk_start}-{chunk_end}: {error_reason}")
                    # Add None placeholders to maintain index alignment
                    all_results.extend([None] * len(chunk_locations))
                    continue
                
                # Handle response - Open-Meteo returns a single dict with arrays when multiple locations are requested
                chunk_results = []
                
                if isinstance(data, dict):
                    # Check if this is a batch response (has arrays for latitude/longitude)
                    if 'latitude' in data and isinstance(data.get('latitude'), list):
                        # Batch response: data contains arrays for each location
                        latitudes_resp = data.get('latitude', [])
                        longitudes_resp = data.get('longitude', [])
                        current_data = data.get('current', {})
                        
                        if not isinstance(current_data, dict):
                            logger.warning(f"Invalid current data format in batch response for chunk {chunk_start}-{chunk_end}")
                            all_results.extend([None] * len(chunk_locations))
                            continue
                        
                        # Process each location in the chunk
                        num_locations = min(len(latitudes_resp), len(chunk_locations))
                        for i in range(num_locations):
                            try:
                                lat = latitudes_resp[i]
                                lon = longitudes_resp[i]
                                
                                # Extract current data for this location (each field is an array)
                                location_current = {}
                                for key, value in current_data.items():
                                    if isinstance(value, list):
                                        if i < len(value):
                                            location_current[key] = value[i]
                                        else:
                                            location_current[key] = None
                                    else:
                                        # Scalar value applies to all locations
                                        location_current[key] = value
                                
                                # Create a response-like structure for this location
                                location_data = {
                                    'latitude': lat,
                                    'longitude': lon,
                                    'timezone': data.get('timezone', timezone),
                                    'current': location_current,
                                }
                                
                                processed = self._format_current_response(location_data, lat, lon)
                                chunk_results.append(processed)
                            except Exception as e:
                                logger.error(f"Error processing location {i} in chunk {chunk_start}-{chunk_end}: {e}")
                                chunk_results.append(None)
                        
                        # Fill remaining slots with None if response had fewer locations
                        while len(chunk_results) < len(chunk_locations):
                            chunk_results.append(None)
                            
                    else:
                        # Single location response (even though we requested multiple)
                        # This can happen if API returns single dict format
                        logger.warning(f"Received single location response for batch chunk {chunk_start}-{chunk_end}")
                        if chunk_locations:
                            lat = chunk_locations[0]['lat']
                            lon = chunk_locations[0]['lon']
                            try:
                                processed = self._format_current_response(data, lat, lon)
                                chunk_results.append(processed)
                                # Fill remaining with None
                                chunk_results.extend([None] * (len(chunk_locations) - 1))
                            except Exception as e:
                                logger.error(f"Error processing single location response: {e}")
                                chunk_results.extend([None] * len(chunk_locations))
                        else:
                            chunk_results.extend([None] * len(chunk_locations))
                elif isinstance(data, list):
                    # API returned a list of response objects
                    logger.debug(f"Received list response for chunk {chunk_start}-{chunk_end}")
                    for i, item in enumerate(chunk_locations):
                        if i < len(data):
                            try:
                                lat = chunk_locations[i]['lat']
                                lon = chunk_locations[i]['lon']
                                processed = self._format_current_response(data[i], lat, lon)
                                chunk_results.append(processed)
                            except Exception as e:
                                logger.error(f"Error processing list item {i}: {e}")
                                chunk_results.append(None)
                        else:
                            chunk_results.append(None)
                else:
                    logger.warning(f"Unexpected response format for chunk {chunk_start}-{chunk_end}: {type(data)}")
                    chunk_results.extend([None] * len(chunk_locations))
                
                all_results.extend(chunk_results)
                
                # Add small delay between chunks to avoid rate limiting
                if chunk_end < len(locations):
                    import time
                    time.sleep(0.5)  # 500ms delay between chunks
                    
            except Exception as e:
                logger.error(f"Error processing batch chunk {chunk_start}-{chunk_end}: {e}", exc_info=True)
                # Add None placeholders for failed chunk
                all_results.extend([None] * len(chunk_locations))
        
        # Filter out None results and return
        valid_results = [r for r in all_results if r is not None]
        logger.info(f"Batch fetch completed: {len(valid_results)}/{len(locations)} locations returned valid data")
        return valid_results if valid_results else []
    
    def fetch_hourly_aqi(
        self,
        latitude: float,
        longitude: float,
        hours: int = 24,
        forecast_days: Optional[int] = None,
        timezone: str = "auto"
    ) -> Optional[Dict]:
        """
        Fetch hourly air quality forecast
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            hours: Number of hours to forecast
            forecast_days: Number of days to forecast (overrides hours if set)
            timezone: Timezone (default: "auto")
            
        Returns:
            Formatted hourly AQI data dictionary
        """
        # Build hourly parameters according to Open-Meteo API documentation
        hourly_params = ','.join([
            'pm10',
            'pm2_5',
            'carbon_monoxide',
            'nitrogen_dioxide',
            'sulphur_dioxide',
            'ozone',
            'dust',
            'uv_index',
            'european_aqi',
            'us_aqi',
        ])
        
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'hourly': hourly_params,
            'timezone': timezone,
        }
        
        # According to Open-Meteo docs: forecast_days (0-16) or forecast_hours (0-240)
        if forecast_days:
            params['forecast_days'] = min(forecast_days, 16)
        else:
            params['forecast_hours'] = min(hours, 240)
        
        data = self._make_request(params)
        if not data:
            return None
        
        return self._format_hourly_response(data, latitude, longitude)
    
    def fetch_daily_aqi(
        self,
        latitude: float,
        longitude: float,
        days: int = 7,
        timezone: str = "auto"
    ) -> Optional[Dict]:
        """
        Fetch daily air quality forecast
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            days: Number of days to forecast (default: 7, max: 16)
            timezone: Timezone (default: "auto")
            
        Returns:
            Formatted daily AQI data dictionary
        """
        # Build daily parameters according to Open-Meteo API documentation
        daily_params = ','.join([
            'pm10',
            'pm2_5',
            'carbon_monoxide',
            'nitrogen_dioxide',
            'sulphur_dioxide',
            'ozone',
            'dust',
            'uv_index',
            'european_aqi',
            'us_aqi',
        ])
        
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'daily': daily_params,
            'forecast_days': min(days, 16),
            'timezone': timezone,
        }
        
        data = self._make_request(params)
        if not data:
            return None
        
        return self._format_daily_response(data, latitude, longitude)
    
    def fetch_enhanced_aqi(
        self,
        latitude: float,
        longitude: float,
        timezone: str = "auto"
    ) -> Optional[Dict]:
        """
        Fetch comprehensive AQI data with all pollutants and calculated AQI values
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            timezone: Timezone (default: "auto")
            
        Returns:
            Enhanced AQI data with calculated EPA AQI values
        """
        # Fetch current and hourly data (168 hours = 7 days for forecast)
        current_data = self.fetch_current_aqi(latitude, longitude, timezone)
        
        if not current_data:
            return None
        
        # Try to fetch hourly data, but don't fail if it's unavailable
        hourly_data = None
        try:
            hourly_data = self.fetch_hourly_aqi(latitude, longitude, forecast_days=7, timezone=timezone)
        except Exception as e:
            print(f"Warning: Could not fetch hourly data: {e}. Continuing with current data only.")
        
        # Enhance with calculated AQI values
        enhanced = self._enhance_with_aqi_calculations(current_data, hourly_data)
        
        # Ingest into RAG system if available
        if AQIRAGSystem:
            try:
                rag = AQIRAGSystem()
                rag.ingest_data(enhanced)
            except Exception as e:
                print(f"RAG Ingestion Warning: {e}")
        
        return enhanced
    
    def _format_current_response(
        self,
        data: Dict,
        latitude: float,
        longitude: float
    ) -> Dict:
        """
        Format current AQI response to match frontend expectations
        
        According to Open-Meteo API docs:
        - API returns european_aqi and us_aqi in current object
        - Use US AQI as primary if available, fallback to European AQI, then calculate from PM2.5
        """
        current = data.get('current', {})
        timezone_info = data.get('timezone', 'UTC')
        
        # Get current pollutant values
        pm25 = current.get('pm2_5', None)
        pm10 = current.get('pm10', None)
        o3 = current.get('ozone', None)
        no2 = current.get('nitrogen_dioxide', None)
        co = current.get('carbon_monoxide', None)
        so2 = current.get('sulphur_dioxide', None)
        
        # Get AQI values from API (preferred over calculated)
        us_aqi = current.get('us_aqi', None)
        european_aqi = current.get('european_aqi', None)
        
        # Determine AQI value: prefer US AQI > European AQI > calculated from PM2.5 > calculated from PM10
        aqi_value = None
        dominant_pollutant = None
        aqi_source = None
        
        if us_aqi is not None:
            aqi_value = us_aqi
            aqi_source = 'us_aqi'
            # Determine dominant pollutant by calculating AQI for each pollutant and finding the highest
            # This is a fallback since we're not requesting sub-indices to avoid API errors
            pollutant_aqis = {}
            if pm25 is not None:
                pollutant_aqis['pm2_5'] = calculate_epa_aqi('pm25', pm25)
            if pm10 is not None:
                pollutant_aqis['pm10'] = calculate_epa_aqi('pm10', pm10)
            if no2 is not None:
                pollutant_aqis['nitrogen_dioxide'] = calculate_epa_aqi('no2', no2)
            if o3 is not None:
                pollutant_aqis['ozone'] = calculate_epa_aqi('o3', o3)
            if so2 is not None:
                pollutant_aqis['sulphur_dioxide'] = calculate_epa_aqi('so2', so2)
            if co is not None:
                pollutant_aqis['carbon_monoxide'] = calculate_epa_aqi('co', co)
            
            if pollutant_aqis:
                max_aqi = max((v for v in pollutant_aqis.values() if v is not None), default=None)
                if max_aqi:
                    dominant_pollutant = next(k for k, v in pollutant_aqis.items() if v == max_aqi)
        elif european_aqi is not None:
            aqi_value = european_aqi
            aqi_source = 'european_aqi'
            # Determine dominant pollutant by calculating AQI for each pollutant
            pollutant_aqis = {}
            if pm25 is not None:
                pollutant_aqis['pm2_5'] = calculate_epa_aqi('pm25', pm25)
            if pm10 is not None:
                pollutant_aqis['pm10'] = calculate_epa_aqi('pm10', pm10)
            if no2 is not None:
                pollutant_aqis['nitrogen_dioxide'] = calculate_epa_aqi('no2', no2)
            if o3 is not None:
                pollutant_aqis['ozone'] = calculate_epa_aqi('o3', o3)
            if so2 is not None:
                pollutant_aqis['sulphur_dioxide'] = calculate_epa_aqi('so2', so2)
            
            if pollutant_aqis:
                max_aqi = max((v for v in pollutant_aqis.values() if v is not None), default=None)
                if max_aqi:
                    dominant_pollutant = next(k for k, v in pollutant_aqis.items() if v == max_aqi)
        elif pm25 is not None:
            # Fallback to calculated AQI from PM2.5
            aqi_value = calculate_epa_aqi('pm25', pm25)
            dominant_pollutant = 'pm2_5'
            aqi_source = 'calculated_pm25'
        elif pm10 is not None:
            # Fallback to calculated AQI from PM10
            aqi_value = calculate_epa_aqi('pm10', pm10)
            dominant_pollutant = 'pm10'
            aqi_source = 'calculated_pm10'
        
        # Get AQI category and info
        aqi_info = get_aqi_category(aqi_value) if aqi_value else {
            'category': 'Unknown',
            'color': '#808080',
            'health_advice': 'Unable to determine air quality.'
        }
        
        # Fetch weather data
        weather_data = self.fetch_weather_data(latitude, longitude, timezone_info)
        
        # Reverse geocode location
        location_info = reverse_geocode(latitude, longitude)
        
        return {
            'location': {
                'lat': latitude,
                'lon': longitude,
                'city': location_info.get('city') if location_info else None,
                'country': location_info.get('country') if location_info else None,
            },
            'timezone': timezone_info,
            'current': {
                'time': current.get('time', ''),
                'pm2_5': pm25,
                'pm10': pm10,
                'ozone': o3,
                'nitrogen_dioxide': no2,
                'carbon_monoxide': co,
                'sulphur_dioxide': so2,
                'dust': current.get('dust', None),
                'uv_index': current.get('uv_index', None),
            },
            'aqi': aqi_value,
            'us_aqi': us_aqi,
            'european_aqi': european_aqi,
            'aqi_source': aqi_source,
            'category': aqi_info['category'],
            'color': aqi_info['color'],
            'health_advice': aqi_info['health_advice'],
            'dominant_pollutant': dominant_pollutant,
            'lastUpdated': current.get('time', ''),
            'weather': weather_data if weather_data else None,
        }
    
    def _format_hourly_response(
        self,
        data: Dict,
        latitude: float,
        longitude: float
    ) -> Dict:
        """
        Format hourly AQI response
        
        According to Open-Meteo API docs:
        - Hourly data includes arrays for each requested parameter
        - Includes european_aqi and us_aqi if requested
        """
        hourly = data.get('hourly', {})
        timezone_info = data.get('timezone', 'UTC')
        
        return {
            'location': {
                'lat': latitude,
                'lon': longitude,
            },
            'timezone': timezone_info,
            'hourly': {
                'time': hourly.get('time', []),
                'pm2_5': hourly.get('pm2_5', []),
                'pm10': hourly.get('pm10', []),
                'ozone': hourly.get('ozone', []),
                'nitrogen_dioxide': hourly.get('nitrogen_dioxide', []),
                'carbon_monoxide': hourly.get('carbon_monoxide', []),
                'sulphur_dioxide': hourly.get('sulphur_dioxide', []),
                'dust': hourly.get('dust', []),
                'uv_index': hourly.get('uv_index', []),
                'european_aqi': hourly.get('european_aqi', []),
                'us_aqi': hourly.get('us_aqi', []),
            },
        }
    
    def _format_daily_response(
        self,
        data: Dict,
        latitude: float,
        longitude: float
    ) -> Dict:
        """
        Format daily AQI response
        
        According to Open-Meteo API docs:
        - Daily data includes arrays for each requested parameter
        - Includes european_aqi and us_aqi if requested
        """
        daily = data.get('daily', {})
        timezone_info = data.get('timezone', 'UTC')
        
        return {
            'location': {
                'lat': latitude,
                'lon': longitude,
            },
            'timezone': timezone_info,
            'daily': {
                'time': daily.get('time', []),
                'pm2_5': daily.get('pm2_5', []),
                'pm10': daily.get('pm10', []),
                'ozone': daily.get('ozone', []),
                'nitrogen_dioxide': daily.get('nitrogen_dioxide', []),
                'carbon_monoxide': daily.get('carbon_monoxide', []),
                'sulphur_dioxide': daily.get('sulphur_dioxide', []),
                'dust': daily.get('dust', []),
                'uv_index': daily.get('uv_index', []),
                'european_aqi': daily.get('european_aqi', []),
                'us_aqi': daily.get('us_aqi', []),
            },
        }
    
    def _enhance_with_aqi_calculations(
        self,
        current_data: Dict,
        hourly_data: Optional[Dict]
    ) -> Dict:
        """
        Enhance AQI data with calculated EPA AQI values for each pollutant
        """
        if not current_data:
            raise ValueError("current_data must be provided")
        
        current = current_data.get('current', {})
        if not isinstance(current, dict):
            current = {}
        
        # Calculate AQI for each pollutant
        pollutants_data = {}
        
        pm25 = current.get('pm2_5')
        if pm25 is not None:
            aqi_pm25 = calculate_epa_aqi('pm25', pm25)
            pollutants_data['pm25'] = {
                'value': pm25,
                'unit': 'µg/m³',
                'epa_aqi': aqi_pm25,
                'category': get_aqi_category(aqi_pm25)['category'] if aqi_pm25 else None,
                'color': get_aqi_category(aqi_pm25)['color'] if aqi_pm25 else None,
            }
        
        pm10 = current.get('pm10')
        if pm10 is not None:
            aqi_pm10 = calculate_epa_aqi('pm10', pm10)
            pollutants_data['pm10'] = {
                'value': pm10,
                'unit': 'µg/m³',
                'epa_aqi': aqi_pm10,
                'category': get_aqi_category(aqi_pm10)['category'] if aqi_pm10 else None,
                'color': get_aqi_category(aqi_pm10)['color'] if aqi_pm10 else None,
            }
        
        o3 = current.get('ozone')
        if o3 is not None:
            aqi_o3 = calculate_epa_aqi('o3', o3)
            pollutants_data['o3'] = {
                'value': o3,
                'unit': 'µg/m³',
                'epa_aqi': aqi_o3,
                'category': get_aqi_category(aqi_o3)['category'] if aqi_o3 else None,
                'color': get_aqi_category(aqi_o3)['color'] if aqi_o3 else None,
            }
        
        no2 = current.get('nitrogen_dioxide')
        if no2 is not None:
            aqi_no2 = calculate_epa_aqi('no2', no2)
            pollutants_data['no2'] = {
                'value': no2,
                'unit': 'µg/m³',
                'epa_aqi': aqi_no2,
                'category': get_aqi_category(aqi_no2)['category'] if aqi_no2 else None,
                'color': get_aqi_category(aqi_no2)['color'] if aqi_no2 else None,
            }
        
        co = current.get('carbon_monoxide')
        if co is not None:
            aqi_co = calculate_epa_aqi('co', co)
            pollutants_data['co'] = {
                'value': co,
                'unit': 'µg/m³',
                'epa_aqi': aqi_co,
                'category': get_aqi_category(aqi_co)['category'] if aqi_co else None,
                'color': get_aqi_category(aqi_co)['color'] if aqi_co else None,
            }
        
        so2 = current.get('sulphur_dioxide')
        if so2 is not None:
            aqi_so2 = calculate_epa_aqi('so2', so2)
            pollutants_data['so2'] = {
                'value': so2,
                'unit': 'µg/m³',
                'epa_aqi': aqi_so2,
                'category': get_aqi_category(aqi_so2)['category'] if aqi_so2 else None,
                'color': get_aqi_category(aqi_so2)['color'] if aqi_so2 else None,
            }
        
        # Determine dominant pollutant (highest AQI)
        dominant_pollutant = None
        max_aqi = 0
        
        for pollutant, data in pollutants_data.items():
            if 'epa_aqi' in data and data['epa_aqi'] and data['epa_aqi'] > max_aqi:
                max_aqi = data['epa_aqi']
                dominant_pollutant = pollutant
        
        # Get overall AQI info
        overall_aqi = pollutants_data.get(dominant_pollutant, {}).get('epa_aqi') if dominant_pollutant else None
        aqi_info = get_aqi_category(overall_aqi) if overall_aqi else {
            'category': 'Unknown',
            'color': '#808080',
            'health_advice': 'Unable to determine air quality.'
        }
        
        # Generate health recommendations
        health_recommendations = []
        if overall_aqi:
            if overall_aqi <= 50:
                health_recommendations = [
                    'Air quality is good. Enjoy outdoor activities.',
                    'No special precautions needed.'
                ]
            elif overall_aqi <= 100:
                health_recommendations = [
                    'Air quality is acceptable for most people.',
                    'Sensitive individuals should consider reducing prolonged outdoor exertion.'
                ]
            elif overall_aqi <= 150:
                health_recommendations = [
                    'Sensitive groups should reduce outdoor activities.',
                    'Children, elderly, and those with respiratory conditions should take extra care.'
                ]
            elif overall_aqi <= 200:
                health_recommendations = [
                    'Everyone should reduce prolonged outdoor exertion.',
                    'Sensitive groups should avoid outdoor activities.',
                    'Keep windows closed if possible.'
                ]
            else:
                health_recommendations = [
                    'Avoid all outdoor activities.',
                    'Stay indoors with windows closed.',
                    'Use air purifiers if available.',
                    'Consider wearing N95 masks if going outside is necessary.'
                ]
        

        # Calculate daily aggregates from hourly data
        daily_agg = {}
        if hourly_data and 'hourly' in hourly_data:
            h = hourly_data['hourly']
            times = h.get('time', [])
            count = len(times)
            days = count // 24 if count >= 24 else 0
            
            daily_agg['time'] = []
            pollutants = ['pm2_5', 'pm10', 'ozone', 'nitrogen_dioxide', 'sulphur_dioxide', 'carbon_monoxide']
            for p in pollutants:
                 daily_agg[p] = []

            for d in range(days):
                start = d * 24
                end = start + 24
                # Date (Use 12th hour for representative date/time)
                if start < count:
                     mid = start + 12
                     daily_agg['time'].append(times[mid] if mid < count else times[start])
                
                # Pollutants
                for p in pollutants:
                    vals = h.get(p, [])
                    if vals and len(vals) > start:
                        chunk = vals[start:end]
                        valid = [v for v in chunk if v is not None]
                        if valid:
                            # Use Max for pollutants to be conservative
                            daily_agg[p].append(max(valid))
                        else:
                             daily_agg[p].append(None)

        return {
            'location': current_data.get('location', {}),
            'timezone': current_data.get('timezone', 'UTC'),
            'aqi': {
                'local_epa_aqi': {
                    'value': overall_aqi,
                    'category': aqi_info['category'],
                    'color': aqi_info['color'],
                } if overall_aqi else None,
                'uaqi': {
                    'value': overall_aqi,
                    'category': aqi_info['category'],
                    'color': aqi_info['color'],
                } if overall_aqi else None,
                'national_aqi': {
                    'value': overall_aqi,
                    'category': aqi_info['category'],
                    'color': aqi_info['color'],
                } if overall_aqi else None,
            },
            'pollutants': pollutants_data,
            'dominant_pollutant': dominant_pollutant,
            'health_recommendations': health_recommendations,
            'lastUpdated': current.get('time', ''),
            'current': current,
            'hourly': hourly_data.get('hourly', {}) if hourly_data else {},
            'daily': daily_agg,
        }

