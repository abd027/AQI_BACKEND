Write-Host "Starting Django server with WebSocket support (Daphne)..." -ForegroundColor Green
Write-Host ""
Write-Host "Make sure Redis is running before starting!" -ForegroundColor Yellow
Write-Host ""
daphne -b 0.0.0.0 -p 8000 breatheasy.asgi:application


