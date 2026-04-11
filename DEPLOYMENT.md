# Deploying RAG System on papers.mccv.at

## Prerequisites
- Server with Docker and Docker Compose installed
- Domain `papers.mccv.at` with DNS A record pointing to your server IP
- Existing app on `www.mccv.at` running in Docker

## Architecture

Traefik reverse proxy sits in front of all services, handles SSL termination
and routes traffic by domain name:

```
Internet → Traefik (ports 80/443)
             ├── www.mccv.at    → existing app
             └── papers.mccv.at → RAG frontend (nginx)
                                    └── /api/* → RAG backend (FastAPI)
```

## Step 1: DNS

Add an A record for `papers.mccv.at` pointing to your server's public IP.
Verify propagation:

```bash
dig papers.mccv.at +short
```

## Step 2: Create shared Docker network

```bash
docker network create web
```

## Step 3: Set up Traefik

Copy the `traefik/` directory to your server (e.g., `/opt/traefik/`).

Edit `traefik.yml` and replace `your-email@example.com` with your real email
(used for Let's Encrypt certificate expiry notifications).

```bash
cd /opt/traefik
docker compose up -d
```

## Step 4: Update your existing app

Your existing app currently binds to port 80 directly. It needs to move behind
Traefik instead. In its `docker-compose.yml`:

1. **Remove** the `ports:` section (e.g., `- "80:80"`)
2. **Add** the external `web` network and Traefik labels:

```yaml
services:
  your-app:
    # ... existing config ...
    networks:
      - web
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.your-app.rule=Host(`www.mccv.at`) || Host(`mccv.at`)"
      - "traefik.http.routers.your-app.entrypoints=websecure"
      - "traefik.http.routers.your-app.tls.certresolver=letsencrypt"
      - "traefik.http.services.your-app.loadbalancer.server.port=80"

networks:
  web:
    external: true
```

Then restart it:

```bash
docker compose up -d
```

## Step 5: Deploy the RAG system

1. Clone/copy this repo to the server
2. Create your `.env` file with API keys (see `.env.example`)
3. Start the stack:

```bash
cd /path/to/rag-system
docker compose up -d --build
```

## Verification

```bash
# Check Traefik is running
docker compose -f /opt/traefik/docker-compose.yml logs

# Check SSL and frontend
curl -I https://papers.mccv.at

# Check backend API through frontend proxy
curl https://papers.mccv.at/api/health

# Check existing site still works
curl -I https://www.mccv.at
```

## Troubleshooting

- **Certificate errors**: Ensure DNS is propagated and port 443 is open. Check
  Traefik logs: `docker compose -f /opt/traefik/docker-compose.yml logs -f`
- **502 Bad Gateway**: The target container isn't reachable. Check it's on the
  `web` network: `docker network inspect web`
- **API calls fail**: Check that the `internal` network connects frontend and
  backend: `docker compose logs frontend`
