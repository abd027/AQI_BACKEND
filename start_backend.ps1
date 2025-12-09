# PowerShell script to activate venv and run migrations

Write-Host "Activating virtual environment..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

Write-Host ""
Write-Host "Running database migrations..." -ForegroundColor Green
python manage.py migrate

Write-Host ""
Write-Host "Starting Django development server..." -ForegroundColor Green
python manage.py runserver 8000
