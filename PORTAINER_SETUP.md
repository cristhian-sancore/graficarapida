# 🌐 Guia de Implantação no Portainer (Redes Docker + Cloudflare + PostgreSQL)

Este documento ensina como implantar a **Gráfica Rápida Express** no **Portainer** com criação automática das redes **`grafica`** e **`REDE`**.

---

## 📋 Stack do Portainer (Copie e Cole)

No seu **Portainer**, vá em **Stacks** ➔ **Add stack** (ou edite a stack existente) e cole esta configuração atualizada:

```yaml
version: '3.8'

services:
  # BANCO DE DADOS POSTGRESQL (Conectado à rede isolada 'grafica')
  postgres-db:
    image: postgres:15-alpine
    container_name: grafica_postgres
    restart: always
    environment:
      POSTGRES_DB: graficadb
      POSTGRES_USER: graficauser
      POSTGRES_PASSWORD: graficapassword2026
    ports:
      - "5432:5432"
    networks:
      - grafica
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U graficauser -d graficadb"]
      interval: 5s
      timeout: 5s
      retries: 5

  # APLICAÇÃO WEB DA GRÁFICA RÁPIDA (Conectada às redes 'grafica' e 'REDE' do Cloudflare)
  grafica-express:
    image: ghcr.io/cristhian-sancore/graficarapida:latest
    container_name: grafica_rapida_portainer
    restart: always
    ports:
      - "8050:8050"
    environment:
      - PORT=8050
      - FLASK_ENV=production
      - DATABASE_URL=postgresql://graficauser:graficapassword2026@postgres-db:5432/graficadb
    depends_on:
      postgres-db:
        condition: service_healthy
    networks:
      - grafica
      - REDE
    volumes:
      - grafica_uploads_data:/app/static/uploads

networks:
  grafica:
    name: grafica
    driver: bridge
  REDE:
    name: REDE
    driver: bridge

volumes:
  postgres_data:
    driver: local
  grafica_uploads_data:
    driver: local
```

---

## 🔗 Resolução do Erro "network REDE declared as external, but could not be found":

Ao definir `driver: bridge` para a rede **`REDE`**, o Docker Compose cria e gerencia a rede automaticamente na primeira implantação, eliminando o erro de rede externa não encontrada.
