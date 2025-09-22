@echo off# Build and start the services
echo Building and starting services...
docker-compose up -d canonical-server edge-server-0 edge-server-1 edge-server-2EM Start the distributed computing system
echo Starting Distributed Computing System...
echo ==================================

REM Stop any existing containers
echo Stopping any existing containers...
docker-compose down

REM Build and start the services
echo Building and starting services...
docker-compose up -d canonical-server edge-server-1 edge-server-2 edge-server-3

REM Wait for services to start
echo Waiting for services to start...
timeout /t 10 /nobreak > nul

REM Show service status
echo Service Status:
docker-compose ps

echo.
echo ==================================
echo System Started Successfully!
echo.
echo Services available:
echo - Canonical Server: localhost:9000
echo - Edge Server 0: localhost:8001
echo - Edge Server 1: localhost:8002
echo - Edge Server 2: localhost:8003
echo.
echo To view logs: docker-compose logs -f [service-name]
echo To run client: docker-compose run --rm client
echo To stop system: docker-compose down
echo ==================================
pause