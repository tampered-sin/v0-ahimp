@echo off
setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
set "BACKEND_DIR=%ROOT%backend"
set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
set "POSTGRES_URL=postgresql://ahimp_user:ahimp_secure_password_2024@localhost:5432/ahimp"
set "PG_HEALTH=unknown"

where pnpm >nul 2>nul
if %errorlevel%==0 (
  set "FRONTEND_CMD=pnpm dev"
) else (
  set "FRONTEND_CMD=npm run dev"
)

where docker >nul 2>nul
if not %errorlevel%==0 (
  echo [WARN] Docker CLI not found. Backend will try PostgreSQL at localhost:5432.
) else (
  if exist "%ROOT%docker-compose.yml" (
    pushd "%ROOT%"
    docker compose up -d postgres >nul 2>nul
    if not !errorlevel!==0 (
      docker-compose up -d postgres >nul 2>nul
    )
    popd
  ) else (
    docker run --name ahimp_postgres -e POSTGRES_DB=ahimp -e POSTGRES_USER=ahimp_user -e POSTGRES_PASSWORD=ahimp_secure_password_2024 -p 5432:5432 -d postgres:15-alpine >nul 2>nul
    if not !errorlevel!==0 (
      docker start ahimp_postgres >nul 2>nul
    )
  )

  for /L %%I in (1,1,30) do (
    for /f "delims=" %%S in ('docker inspect -f "{{.State.Health.Status}}" ahimp_postgres 2^>nul') do (
      set "PG_HEALTH=%%S"
    )
    if /I "!PG_HEALTH!"=="healthy" goto :postgres_ready
    if %%I==1 echo Waiting for PostgreSQL container health...
    timeout /t 2 /nobreak >nul
  )
)

:postgres_ready
if /I not "!PG_HEALTH!"=="healthy" (
  echo [WARN] PostgreSQL container health is '!PG_HEALTH!'. Backend startup may fail if DB is not ready.
)

if exist "%PYTHON_EXE%" (
  start "AHIMP Backend" powershell -NoExit -Command "Set-Location '%BACKEND_DIR%'; $env:DATABASE_URL='%POSTGRES_URL%'; & '%PYTHON_EXE%' -m uvicorn main:app --reload --port 9000"
) else (
  start "AHIMP Backend" powershell -NoExit -Command "Set-Location '%BACKEND_DIR%'; $env:DATABASE_URL='%POSTGRES_URL%'; python -m uvicorn main:app --reload --port 9000"
)

start "AHIMP Frontend" powershell -NoExit -Command "Set-Location '%ROOT%'; %FRONTEND_CMD%"

echo Started backend and frontend.
echo PostgreSQL: docker service 'postgres' (container: ahimp_postgres)
echo Backend: http://localhost:9000
echo Frontend: http://localhost:3000
echo Close both PowerShell windows to stop the servers.
