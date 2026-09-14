# 🌐 Guia de Implantação no Portainer (Redes Docker + Cloudflare + PostgreSQL)

Este documento ensina como implantar a **Gráfica Rápida Express** no **Portainer** utilizando a rede isolada de banco de dados **`grafica`** e conectando-se à rede existente **`REDE`** do **Cloudflare Tunnel / Reverse Proxy**.

---

## 📋 Stack do Portainer (Copie e Cole)

No seu **Portainer**, vá em **Stacks** ➔ **Add stack** (ou edite a stack existente) e cole esta configuração:

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
    external: true

volumes:
  postgres_data:
    driver: local
  grafica_uploads_data:
    driver: local
```

---

## 🔗 Detalhes da Conexão de Redes:

1. **Rede `grafica`**: Rede bridge exclusiva para a comunicação de alta velocidade entre a aplicação web e o banco PostgreSQL.
2. **Rede `REDE`**: Conecta o container `grafica_rapida_portainer` ao Cloudflare Tunnel / Proxy já existente no seu servidor, permitindo que a URL `https://grafica.cristhiansancore.com.br` roteie o tráfego diretamente para `http://grafica_rapida_portainer:8050` ou `http://grafica-express:8050`!
