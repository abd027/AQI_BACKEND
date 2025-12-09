@echo off
REM Activate virtual environment and run migrations

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Running database migrations...
python manage.py migrate

echo.
echo Starting Django development server...
python manage.py runserver 8000
