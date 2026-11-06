Copy-Item -ErrorAction SilentlyContinue .env.example .env
docker compose up -d --build
Write-Host "API: http://localhost:8000/docs"
Write-Host "Web: http://localhost:3000"
