# Docker Setup Guide for AHIMP

## Overview

This project uses **Docker Compose** to orchestrate PostgreSQL and the FastAPI backend. This ensures consistency across development, testing, and production environments.

## Prerequisites

- **Docker**: [Install Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Docker Compose**: Included with Docker Desktop
- **Git**: For cloning the repository

## Quick Start

### 1. Start the Services

```bash
# From the project root (where docker-compose.yml is located)
docker-compose up --build
```

**First run will**:
1. Build the backend image
2. Start PostgreSQL container
3. Create the database
4. Seed 20 years of synthetic data (~7.3M records)
5. Train ML models (5-10 minutes)
6. Expose APIs at `http://localhost:9000`

### 2. Access the Application

- **API Docs**: http://localhost:9000/docs (Swagger UI)
- **Database**: `localhost:5432` (PostgreSQL)
  - User: `ahimp_user`
  - Password: `ahimp_secure_password_2024`
  - Database: `ahimp`

### 3. Monitor Progress

```bash
# Watch backend logs
docker-compose logs -f backend

# Watch PostgreSQL logs
docker-compose logs -f postgres

# View all services
docker-compose ps
```

---

## Common Docker Commands

### Development

```bash
# Start services in foreground (see logs)
docker-compose up

# Start services in background
docker-compose up -d

# View logs
docker-compose logs -f backend
docker-compose logs backend  # latest 100 lines

# Rebuild images (after code changes)
docker-compose up --build

# Rebuild without cache
docker-compose up --build --no-cache
```

### Stopping & Cleanup

```bash
# Stop services (keeps data volumes)
docker-compose stop

# Stop and remove containers
docker-compose down

# Remove everything (including database data)
docker-compose down -v

# Remove all dangling images
docker image prune -a
```

### Database Management

```bash
# Connect to PostgreSQL CLI
docker-compose exec postgres psql -U ahimp_user -d ahimp

# Run SQL query
docker-compose exec postgres psql -U ahimp_user -d ahimp -c "SELECT COUNT(*) FROM consumption_records;"

# Create database dump
docker-compose exec postgres pg_dump -U ahimp_user -d ahimp > ahimp_backup.sql

# Restore from dump
docker-compose exec -T postgres psql -U ahimp_user -d ahimp < ahimp_backup.sql
```

### Debugging

```bash
# Execute command in running container
docker-compose exec backend bash

# View container resource usage
docker stats

# Inspect container details
docker-compose exec backend env

# Check network connectivity
docker-compose exec backend ping postgres
```

---

## Docker Compose Configuration

The `docker-compose.yml` defines two services:

### PostgreSQL Service
```yaml
- Image: postgres:15-alpine (lightweight)
- Port: 5432 (internal: 5432, external: 5432)
- Volume: postgres_data (persistent storage)
- Health Check: Every 10s
- Network: ahimp_network (internal bridge)
```

### Backend Service
```yaml
- Build: From ./backend/Dockerfile
- Port: 8000 (FastAPI)
- Depends On: PostgreSQL (waits for healthy status)
- Environment: DATABASE_URL set automatically
- Command: uvicorn with --reload for development
```

---

## Troubleshooting

### Issue: "PostgreSQL connection refused"

**Solution**:
```bash
# Ensure PostgreSQL is healthy
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres

# Wait 10s for health check to pass
```

### Issue: "Port 5432 already in use"

**Solution**:
```bash
# Option 1: Use different port (edit docker-compose.yml)
# ports:
#   - "5433:5432"

# Option 2: Stop other PostgreSQL instances
docker ps | grep postgres
docker stop <container_id>
```

### Issue: "Port 8000 already in use"

**Solution**:
```bash
# Find process using port 8000
netstat -tulpn | grep 8000

# Kill the process
kill -9 <PID>

# Or use different port (edit docker-compose.yml)
```

### Issue: ML Models training very slow

**This is normal on first boot with 20-year data**:
- XGBoost training: ~5-7 minutes (7.3M records)
- Patience: Subsequent boots use cached models
- Check logs: `docker-compose logs -f backend`

### Issue: "Out of memory" during training

**Solutions**:
- Increase Docker Desktop memory (Settings → Resources)
- Reduce data: Modify `seed.py` `start_date` to 2-5 years
- Use SQLite temporarily: `DATABASE_URL=sqlite:///ahimp.db`

### Persistent Data Lost After `docker-compose down -v`

**To backup before destroying**:
```bash
docker-compose exec postgres pg_dump -U ahimp_user -d ahimp > backup.sql
docker-compose down -v
# Later: restore with the "Restore from dump" command above
```

---

## Performance Tuning

### PostgreSQL Optimization

Edit `docker-compose.yml`:
```yaml
postgres:
  environment:
    POSTGRES_INITDB_ARGS: "-c shared_buffers=256MB -c max_connections=200"
```

### Backend Optimization

For production, modify `docker-compose.yml`:
```yaml
backend:
  command: gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

---

## Environment Variables

Create a `.env` file in the project root:

```bash
# Optional: Override defaults (already set in docker-compose.yml)
DATABASE_URL=postgresql://ahimp_user:ahimp_secure_password_2024@postgres:5432/ahimp
POSTGRES_DB=ahimp
POSTGRES_USER=ahimp_user
POSTGRES_PASSWORD=ahimp_secure_password_2024
PYTHONUNBUFFERED=1
```

---

## Production Deployment

For production, modify `docker-compose.yml`:

```yaml
backend:
  build: ./backend
  restart: always
  ports:
    - "8000:8000"
  environment:
    DATABASE_URL: postgresql://user:securepass@postgres:5432/ahimp
  command: uvicorn main:app --host 0.0.0.0 --port 8000

postgres:
  restart: always
  volumes:
    - postgres_data:/var/lib/postgresql/data
```

Then deploy with:
```bash
docker-compose -f docker-compose.yml up -d
```

---

## Useful Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Docker Images](https://hub.docker.com/_/postgres)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
