# One HTTPS address (Caddy) and the production compose file

In production everything is served from **one HTTPS address**, for example
`https://matters.yourfirm.mx`:

| Path | Goes to |
|---|---|
| `/` | the web app (frontend) |
| `/api/*` | the backend (the `/api` prefix is removed first) |
| `/mcp` | the MCP server that AI assistants connect to |

Caddy (`deploy/Caddyfile`) gets and renews the HTTPS certificate by itself,
redirects HTTP to HTTPS, adds security headers (HSTS, a strict
Content-Security-Policy, no framing), compresses responses, and refuses request
bodies above `MAX_REQUEST_MB` (default 64, just over the 50 MB upload limit).

Only ports **80 and 443** are open. Postgres, MinIO, Qdrant, the backend, the
ingestion worker, the MCP server and the web app have no published ports.

## Start it

Needs a server where `DOMAIN` already resolves to the server's IP address (the
certificate is requested for it) and ports 80 and 443 are reachable.

```bash
# .env  (see .env.example; python scripts/generate_env.py creates the secrets)
DOMAIN=matters.yourfirm.mx

docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

What the production file changes: adds Caddy; removes every other published
port; serves the app and API from one address (so no CORS); marks session
cookies `Secure`; turns the API docs off; passes the real client address
through so the audit log records it; builds the web app to call `/api` and to
show the page's own address as the AI connection address; restarts everything
automatically after a crash or reboot.

## Try it on a laptop

```bash
DOMAIN=localhost docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Caddy then uses its own local certificate authority, so a browser warns about
the certificate (use `curl -k`, or trust Caddy's root certificate from the
`caddy_data` volume). Go back to the normal development setup with
`docker compose -f docker-compose.yml -f docker-compose.prod.yml down` followed
by `docker compose up -d`.

## Administration without open ports

The MinIO console and the database are not reachable from outside. Use an SSH
tunnel from your computer, for example
`ssh -L 9001:localhost:9001 user@server` after temporarily adding a localhost
port mapping, or run `docker compose exec` on the server.
