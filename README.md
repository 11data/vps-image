# RunYourAgent VPS Image

Docker Compose configuration for running OpenClaw Gateway + Mission Control API + PostgreSQL on provisioned VPS instances.

## Quick Start

```bash
# Clone this repository
git clone https://github.com/runyouragent/vps-image.git /opt/vps-image
cd /opt/vps-image

# Copy environment template
cp .env.example .env

# Edit .env with your values
nano .env

# Start services
docker compose up -d

# Check logs
docker compose logs -f

# Check status
docker compose ps
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| `openclaw` | 18789 | OpenClaw Gateway |
| `mission-control` | 18790 | Mission Control API |
| `postgres` | 5432 | PostgreSQL database (internal only) |

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENCLAW_GATEWAY_TOKEN` | Auth token for gateway | Yes | - |
| `POSTGRES_PASSWORD` | PostgreSQL password | Yes | - |
| `OPENCLAW_INSTANCE_ID` | Instance identifier | No | `vps` |

## Volumes

| Volume | Description |
|--------|-------------|
| `postgres_data` | PostgreSQL data persistence |
| `openclaw_data` | OpenClaw configuration |
| `openclaw_workspace` | Agent workspace files |

## Health Checks

All services have health checks enabled. Check status with:

```bash
docker compose ps
```

Or check individual services:

```bash
docker compose exec openclow wget -q -O- http://localhost:18789/health
docker compose exec mission-control wget -q -O- http://localhost:18790/health
docker compose exec postgres pg_isready -U clawd
```

## Development

### Building Mission Control Image

```bash
docker build -f Dockerfile.mission-control -t ghcr.io/runyouragent/mission-control:latest .
```

### Testing Changes

```bash
# Stop services
docker compose down

# Rebuild and start
docker compose up -d --build

# View logs
docker compose logs -f mission-control
```

## Troubleshooting

### Services not starting

```bash
# Check logs
docker compose logs

# Check disk space
df -h

# Check Docker
docker ps -a
```

### Database connection issues

```bash
# Check PostgreSQL is running
docker compose exec postgres pg_isready -U clawd

# Check database exists
docker compose exec postgres psql -U clawd -l
```

### Reset everything

```bash
# Stop and remove containers, volumes
docker compose down -v

# Remove images (optional)
docker rmi ghcr.io/runyouragent/openclaw:latest
docker rmi ghcr.io/runyouragent/mission-control:latest

# Start fresh
docker compose up -d
```

## Security Notes

- All services run as non-root user `clawd`
- Only necessary ports are exposed
- Database is not exposed to the internet
- Gateway requires token authentication
- Firewall (ufw) should only allow ports 22, 18789, 18790
