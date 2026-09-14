# 🚀 Guia de Implantação no Portainer (PostgreSQL 15 + GitHub Actions)

Este documento ensina como implantar a **Gráfica Rápida Express** no **Portainer** utilizando banco de dados **PostgreSQL 15 (Produção & Alta Performance)** e a imagem compilada automaticamente via **GitHub Actions**.

---

## ⚡ 1. Como Funciona a Compilação Automática

A cada `git push` para a branch `main`:
1. O **GitHub Actions** compila a imagem Docker com suporte a PostgreSQL (`psycopg2-binary`).
2. A imagem é publicada no **GitHub Container Registry (GHCR)**:
   `ghcr.io/cristhian-sancore/graficarapida:latest`

---

## 📋 2. Stack do Portainer com PostgreSQL 15 (Copie e Cole)

No seu **Portainer**, vá em **Stacks** ➔ **Add stack** (ou selecione a stack existente e clique em **Editor**) e cole a configuração abaixo:

```yaml
version: '3.8'

services:
  # BANCO DE DADOS POSTGRESQL (Produção & Alta Escala)
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
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U graficauser -d graficadb"]
      interval: 5s
      timeout: 5s
      retries: 5

  # APLICAÇÃO WEB DA GRÁFICA RÁPIDA
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
    volumes:
      - grafica_uploads_data:/app/static/uploads

volumes:
  postgres_data:
    driver: local
  grafica_uploads_data:
    driver: local
```

---

## ✨ Vantagens do PostgreSQL 15 nesta Stack:

1. **Alta Concorrência & Escala Empresarial**: Suporta milhares de acessos e pedidos simultâneos sem travamentos de escrita.
2. **Criação Automática do Banco**: O banco `graficadb`, as tabelas de clientes, produtos, pedidos, caixa e configurações são criados automaticamente na primeira inicialização.
3. **Persistência Total**: Os dados ficam armazenados no volume Docker dedicado `postgres_data`.
