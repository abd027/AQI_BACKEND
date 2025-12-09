# Quick Start Guide

## Current Status

✅ Database (`aqi_db`) already exists in your PostgreSQL container  
✅ Docker Compose file updated (removed obsolete version field)  
⚠️ Redis needs to be set up (Docker Hub authentication issue)

## Quick Setup Steps

### 1. Update Environment Variables

The `.env` file has been created. Update it with your database credentials:

**For existing PostgreSQL container (port 5432):**
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aqi_db
```

(Adjust username/password if different)

### 2. Redis Setup Options

**Option A: Fix Docker Hub Login (Recommended)**
```powershell
docker login
# Enter your Docker Hub credentials
# Then run:
docker-compose up -d redis
```

**Option B: Use Local Memory Cache (Development Only)**
If you can't get Redis working, temporarily use local memory cache:

Edit `BackEnd/breatheasy/settings.py` and replace the CACHES section with:
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}
```

This works for development but won't persist between server restarts.

**Option C: Install Redis for Windows**
- Download from: https://github.com/microsoftarchive/redis/releases
- Or use WSL2: `wsl sudo apt-get install redis-server`

### 3. Run Migrations

```powershell
cd BackEnd
python manage.py makemigrations
python manage.py migrate
```

### 4. Create Superuser (Optional)

```powershell
python manage.py createsuperuser
```

### 5. Start Development Server

```powershell
python manage.py runserver
```

The API will be available at: `http://localhost:8000`

## Test the API

### Register a new user:
```powershell
curl -X POST http://localhost:8000/api/auth/register/ `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"test@example.com\",\"username\":\"testuser\",\"password\":\"testpass123\",\"password_confirm\":\"testpass123\"}'
```

### Login:
```powershell
curl -X POST http://localhost:8000/api/auth/login/ `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"test@example.com\",\"password\":\"testpass123\"}'
```

## Troubleshooting

### Database Connection Issues
- Verify PostgreSQL container is running: `docker ps`
- Check database exists: `docker exec -it sonyc_postgres psql -U postgres -c "\l"`
- Verify credentials in `.env` file

### Redis Connection Issues
- If using local memory cache, Redis errors can be ignored
- For production, ensure Redis is properly configured

### Import Errors
- Ensure virtual environment is activated
- Install dependencies: `pip install -r requirements.txt`

## Next Steps

1. ✅ Database is ready
2. ⚠️ Set up Redis (choose one of the options above)
3. ✅ Run migrations
4. ✅ Start server
5. 🎉 Test API endpoints!

