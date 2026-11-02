# AI DevOps Login Application

Containerized login application for practicing:

- Docker
- Docker Compose
- FastAPI
- PostgreSQL
- NGINX
- Prometheus
- Grafana
- Loki
- Alertmanager
- GitHub Actions
- Jenkins
- AWS
- Ollama
- AI-powered incident response

## Application Architecture

Browser
    |
    v
NGINX
    |
    +----> Frontend
    |
    +----> Backend
              |
              v
          PostgreSQL

## Start

docker compose up -d --build

## Check containers

docker compose ps

## Application

http://localhost:8080

## Login

Username:

admin

Password:

admin123
