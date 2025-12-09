# Alternative Setup Instructions

If Docker Compose is having authentication issues, you can use one of these alternatives:

## Option 1: Use Existing PostgreSQL Container

You already have a PostgreSQL container running (`sonyc_postgres`). You can use it instead:

### 1. Create the database in existing container:

```powershell
docker exec -it sonyc_postgres psql -U postgres -c "CREATE DATABASE aqi_db;"
```

### 2. Update your `.env` file:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aqi_db
```

(Adjust the port if your existing container uses a different port)

### 3. For Redis, you can either:

**Option A: Install Redis locally (Windows)**
- Download Redis for Windows from: https://github.com/microsoftarchive/redis/releases
- Or use WSL2 with Redis
- Update `.env`: `REDIS_URL=redis://localhost:6379/0`

**Option B: Use Django's local memory cache (for development only)**
- Update `BackEnd/breatheasy/settings.py`:
  ```python
  CACHES = {
      'default': {
          'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
      }
  }
  ```
- Remove Redis dependency for development

## Option 2: Fix Docker Hub Authentication

### Login to Docker Hub:

```powershell
docker login
```

Enter your Docker Hub credentials. If you don't have an account, create one at https://hub.docker.com/

### Then try docker-compose again:

```powershell
docker-compose up -d
```

## Option 3: Use Local PostgreSQL Installation

If you have PostgreSQL installed locally:

1. Create database:
   ```sql
   CREATE DATABASE aqi_db;
   ```

2. Update `.env`:
   ```env
   DATABASE_URL=postgresql://your_username:your_password@localhost:5432/aqi_db
   ```

3. For Redis, use Option A or B from above.

## Quick Development Setup (No Docker)

For quick development without Docker:

1. **Database**: Use SQLite temporarily (not recommended for production)
   - Comment out PostgreSQL config in `settings.py`
   - Django will use SQLite by default

2. **Cache**: Use local memory cache (see Option 1B above)

3. **Run migrations**:
   ```powershell
   cd BackEnd
   python manage.py makemigrations
   python manage.py migrate
   ```

4. **Start server**:
   ```powershell
   python manage.py runserver
   ```

Note: This setup is for development only. Use PostgreSQL and Redis for production.

