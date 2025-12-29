# Third-Party Licenses

This document lists the third-party software components used in Makapix Club and their respective licenses.

## Major Components

### Piskel - Pixel Art Editor

**Repository:** https://github.com/piskelapp/piskel  
**License:** Apache License 2.0  
**Copyright:** Copyright (c) 2013 Julian Descottes  

Makapix Club integrates Piskel as an embedded pixel art editor. The integration includes modifications to:
- Add custom export functionality for publishing directly to Makapix
- Integrate UI elements for seamless workflow between editor and platform
- Enable editing of existing Makapix artwork
- Configure dimension limits appropriate for the platform

Piskel is hosted as a separate service at `piskel.makapix.club` and communicates with the main Makapix application via the postMessage API.

**License Text:** See https://github.com/piskelapp/piskel/blob/master/LICENSE

---

## Core Framework Dependencies

### Frontend (Next.js / React)

| Package | License | Description |
|---------|---------|-------------|
| Next.js | MIT | React framework for production |
| React | MIT | JavaScript library for building user interfaces |
| TypeScript | Apache 2.0 | Typed superset of JavaScript |
| styled-jsx | MIT | Full CSS support for JSX |

### Backend (Python / FastAPI)

| Package | License | Description |
|---------|---------|-------------|
| FastAPI | MIT | Modern web framework for Python |
| SQLAlchemy | MIT | SQL toolkit and ORM |
| Pydantic | MIT | Data validation using Python type annotations |
| Alembic | MIT | Database migration tool |
| uvicorn | BSD-3-Clause | ASGI web server |

### Background Processing

| Package | License | Description |
|---------|---------|-------------|
| Celery | BSD-3-Clause | Distributed task queue |
| Redis | BSD-3-Clause | In-memory data structure store |

---

## Infrastructure Components

### Message Broker

**Eclipse Mosquitto**  
**License:** Eclipse Public License 2.0 (EPL-2.0) / Eclipse Distribution License 1.0 (EDL-1.0)  
**Website:** https://mosquitto.org/  

MQTT broker for real-time messaging between server, web clients, and physical player devices.

### Reverse Proxy

**Caddy**  
**License:** Apache License 2.0  
**Website:** https://caddyserver.com/  

Automatic HTTPS reverse proxy with Docker integration via caddy-docker-proxy.

### Database

**PostgreSQL**  
**License:** PostgreSQL License (similar to BSD/MIT)  
**Website:** https://www.postgresql.org/  

Relational database for structured data storage.

---

## Development Dependencies

Makapix Club uses numerous development tools and libraries. Complete lists can be found in:

- `web/package.json` - Frontend development and runtime dependencies
- `api/requirements.txt` - Backend Python packages
- `worker/requirements.txt` - Background worker Python packages

All development dependencies retain their original licenses as specified in their respective packages.

---

## Docker Base Images

Makapix Club uses official Docker images:

- `node:20-alpine` (MIT License) - For Next.js frontend
- `python:3.12-slim` (Python Software Foundation License) - For FastAPI backend and worker
- `postgres:16-alpine` (PostgreSQL License) - For database
- `redis:7-alpine` (BSD-3-Clause) - For caching and queues
- `eclipse-mosquitto:2` (EPL-2.0 / EDL-1.0) - For MQTT broker
- `caddy:2-alpine` (Apache 2.0) - For reverse proxy

---

## License Compliance

Makapix Club is committed to open source license compliance. If you believe any license information is missing or incorrect, please open an issue at:

https://github.com/fabkury/makapix/issues

---

## How to Check Dependency Licenses

To generate a current list of all dependencies and their licenses:

### Frontend (Node.js)
```bash
cd web
npm list --all
npx license-checker --summary
```

### Backend (Python)
```bash
cd api
pip-licenses --format=markdown
```

### Worker (Python)
```bash
cd worker
pip-licenses --format=markdown
```

---

*Last Updated: December 2025*
