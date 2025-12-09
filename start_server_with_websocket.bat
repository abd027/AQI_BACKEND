@echo off
echo Starting Django server with WebSocket support (Daphne)...
echo.
echo Make sure Redis is running before starting!
echo.
daphne -b 0.0.0.0 -p 8000 breatheasy.asgi:application


