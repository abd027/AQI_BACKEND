# BreatheEasy Django Backend

A complete Django + DRF backend for the BreatheEasy Air Quality Index (AQI) application. This backend provides JWT authentication, role-based access control, and integration with the Open-Meteo Air Quality API.

## Features

- **JWT Authentication**: Secure token-based authentication using `djangorestframework-simplejwt`
- **Role-Based Access Control**: User and admin roles with custom permissions
- **Email Verification**: Email verification system for new user registrations
- **Password Reset**: Secure password reset functionality via email
- **Open-Meteo AQI Integration**: Real-time air quality data from Open-Meteo API
- **Redis Caching**: Efficient caching of AQI data to reduce API calls
- **PostgreSQL Database**: Production-ready database support
- **RESTful API**: Clean REST endpoints for Next.js frontend
- **CORS Support**: Configured for frontend integration

## Technology Stack

- **Django 5.0+**: Web framework
- **Django REST Framework**: REST API framework
- **djangorestframework-simplejwt**: JWT authentication
- **PostgreSQL**: Database (via psycopg2-binary)
- **Redis**: Caching backend (via django-redis)
- **python-decouple**: Environment variable management

## Project Structure

```
BackEnd/
├── breatheasy/          # Main Django project
│   ├── settings.py      # Django settings
│   ├── urls.py          # Main URL configuration
│   └── ...
├── accounts/            # Authentication app
│   ├── models.py        # Custom User model
│   ├── serializers.py   # Auth serializers
│   ├── views.py         # Auth views
│   ├── urls.py          # Auth URLs
│   └── ...
├── aqi/                 # Air Quality Index app
│   ├── models.py        # AQI models (saved locations)
│   ├── services.py      # Open-Meteo API integration
│   ├── views.py         # AQI endpoints
│   ├── cache.py         # Caching utilities
│   └── ...
├── core/                # Core utilities
│   ├── exceptions.py    # Custom exception handlers
│   └── utils.py         # Shared utilities
├── manage.py
├── requirements.txt
└── README.md
```

## Setup Instructions

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 16+ (or use Docker)
- Redis (or use Docker)
- pip (Python package manager)

### 1. Clone and Navigate to Backend

```bash
cd BackEnd
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Database with Docker

Start PostgreSQL and Redis using Docker Compose:

```bash
# From project root
docker-compose up -d
```

This will start:
- PostgreSQL on port `5433` (database: `aqi_db`)
- Redis on port `6379`

### 5. Environment Variables

Create a `.env` file in the `BackEnd/` directory:

```env
# Django Settings
SECRET_KEY=your-secret-key-here-change-in-production
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (PostgreSQL)
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/aqi_db

# Redis Cache
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Email Configuration (for development, use console backend)
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:3000

# JWT Settings (optional)
JWT_ACCESS_TOKEN_LIFETIME=15
JWT_REFRESH_TOKEN_LIFETIME=1440

# AQI Cache TTL (in seconds)
AQI_CACHE_TTL=300
```

**Important**: Generate a secure `SECRET_KEY` for production:

```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### 6. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Create Superuser (Optional)

```bash
python manage.py createsuperuser
```

### 8. Run Development Server

```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Authentication Endpoints

All authentication endpoints are prefixed with `/api/auth/`

#### Register User
```http
POST /api/auth/register/
Content-Type: application/json

{
  "email": "user@example.com",
  "username": "johndoe",
  "password": "securepassword123",
  "password_confirm": "securepassword123"
}
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "johndoe",
  "is_active": true,
  "is_verified": false,
  "created_at": "2025-12-06T12:00:00Z"
}
```

#### Login
```http
POST /api/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "Bearer"
}
```

#### Refresh Token
```http
POST /api/auth/refresh/
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### Logout
```http
POST /api/auth/logout/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### Get Current User
```http
GET /api/auth/me/
Authorization: Bearer <access_token>
```

#### Verify Email
```http
POST /api/auth/verify-email/?token=<verification_token>
```

#### Resend Verification Email
```http
POST /api/auth/resend-verification/
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### Forgot Password
```http
POST /api/auth/forgot-password/
Content-Type: application/json

{
  "email": "user@example.com"
}
```

#### Reset Password
```http
POST /api/auth/reset-password/
Content-Type: application/json

{
  "token": "<reset_token>",
  "new_password": "newsecurepassword123"
}
```

### AQI Endpoints

All AQI endpoints require authentication (Bearer token) and are prefixed with `/api/`

#### Fetch AQI Data
```http
GET /api/aqi/?lat=40.7128&lon=-74.0060&type=current
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `lat` (required): Latitude (-90 to 90)
- `lon` (required): Longitude (-180 to 180)
- `type` (optional): `current`, `hourly`, or `daily` (default: `current`)
- `hours` (optional): Number of hours for hourly forecast (1-240, default: 24)
- `days` (optional): Number of days for daily forecast (1-16, default: 7)

#### Fetch AQI by Coordinates
```http
GET /api/aqi/coordinates/?lat=40.7128&lng=-74.0060
Authorization: Bearer <access_token>
```

#### Fetch Enhanced AQI
```http
GET /api/aqi/enhanced/?lat=40.7128&lng=-74.0060
Authorization: Bearer <access_token>
```

**Response includes:**
- Calculated EPA AQI values for each pollutant
- Health recommendations
- Dominant pollutant
- Category and color coding

#### Fetch AQI Trend
```http
GET /api/aqi/trend/?city=New York
Authorization: Bearer <access_token>
```

#### Get City Rankings
```http
GET /api/cities/rankings/
Authorization: Bearer <access_token>
```

#### Batch AQI Request
```http
POST /api/aqi/batch/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "locations": [
    {"lat": 40.7128, "lng": -74.0060, "city": "New York"},
    {"lat": 51.5074, "lng": -0.1278, "city": "London"}
  ]
}
```

#### Batch Enhanced AQI Request
```http
POST /api/aqi/batch/enhanced/
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "locations": [
    {"lat": 40.7128, "lng": -74.0060},
    {"lat": 51.5074, "lng": -0.1278}
  ]
}
```

## JWT Token Flow

1. **Registration/Login**: User receives `access_token` and `refresh_token`
2. **API Requests**: Include `Authorization: Bearer <access_token>` header
3. **Token Refresh**: When access token expires, use `refresh_token` to get new tokens
4. **Logout**: Blacklist the `refresh_token` to invalidate session

### Token Lifetimes

- **Access Token**: 15 minutes (configurable via `JWT_ACCESS_TOKEN_LIFETIME`)
- **Refresh Token**: 24 hours (configurable via `JWT_REFRESH_TOKEN_LIFETIME`)

## Caching

AQI data is cached in Redis to reduce external API calls:

- **Cache TTL**: 5 minutes (configurable via `AQI_CACHE_TTL`)
- **Cache Key**: Based on latitude, longitude, and data type
- **Automatic**: Caching is handled automatically by the service layer

## Database Models

### User Model

Custom user model with:
- Email and username authentication
- Role field (`user` or `admin`)
- Email verification tokens
- Password reset tokens
- Timestamps (date_joined, last_login)

### SavedLocation Model

Optional model for user's saved locations:
- User foreign key
- Location name, coordinates
- City and country information

## Testing

Run tests (when implemented):

```bash
python manage.py test
```

## Production Deployment

### Security Checklist

1. **Set `DEBUG=False`** in production
2. **Generate secure `SECRET_KEY`** and store in environment variables
3. **Use HTTPS** for all API endpoints
4. **Configure proper CORS** origins (remove `localhost` in production)
5. **Use production email backend** (SMTP) instead of console
6. **Set up proper database backups**
7. **Configure Redis persistence** for production
8. **Use environment variables** for all sensitive data
9. **Enable rate limiting** (consider using DRF throttling)
10. **Set up monitoring and logging**

### Environment Variables for Production

```env
DEBUG=False
SECRET_KEY=<generated-secret-key>
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
DATABASE_URL=postgresql://user:password@db-host:5432/aqi_db
REDIS_URL=redis://redis-host:6379/0
CORS_ALLOWED_ORIGINS=https://yourdomain.com
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
FRONTEND_URL=https://yourdomain.com
```

### Running Migrations in Production

```bash
python manage.py migrate
python manage.py collectstatic  # If using static files
```

## Troubleshooting

### Database Connection Issues

- Ensure PostgreSQL is running: `docker ps`
- Check database credentials in `.env`
- Verify port 5433 is not blocked

### Redis Connection Issues

- Ensure Redis is running: `docker ps`
- Check Redis URL in `.env`
- Test connection: `redis-cli ping`

### Import Errors

- Ensure virtual environment is activated
- Install dependencies: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.10+)

### JWT Token Issues

- Verify token is included in `Authorization` header
- Check token expiration
- Ensure `djangorestframework-simplejwt` is installed

## API Documentation

For interactive API documentation, consider adding:
- **drf-spectacular** for OpenAPI 3.0 schema
- **drf-yasg** for Swagger/OpenAPI documentation

Example installation:
```bash
pip install drf-spectacular
```

Add to `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    ...
    'drf_spectacular',
]
```

Add to `REST_FRAMEWORK` settings:
```python
REST_FRAMEWORK = {
    ...
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

## License

This project is part of the BreatheEasy application suite.

## Support

For issues and questions, please refer to the project documentation or contact the development team.

