@echo off
echo Testing Distributed Computing System...
echo =====================================

echo 1. Starting system...
docker-compose up -d canonical-server edge-server-1 edge-server-2 edge-server-3

echo 2. Waiting for services to initialize...
timeout /t 15 /nobreak > nul

echo 3. Checking service status...
docker-compose ps

echo 4. Testing connectivity...
echo Testing canonical server...
docker-compose exec -T canonical-server python -c "print('Canonical server is running')"

echo Testing edge servers...
docker-compose exec -T edge-server-1 python -c "print('Edge server 1 is running')"
docker-compose exec -T edge-server-2 python -c "print('Edge server 2 is running')"
docker-compose exec -T edge-server-3 python -c "print('Edge server 3 is running')"

echo.
echo =====================================
echo System test completed!
echo To run interactive client: docker-compose run --rm client
echo To view logs: docker-compose logs -f
echo To stop system: docker-compose down
echo =====================================
pause