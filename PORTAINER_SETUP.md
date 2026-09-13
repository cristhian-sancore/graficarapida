# 🚢 Guia de Implantação no Portainer (GitHub Actions + GHCR)

Este documento ensina como implantar a **Gráfica Rápida Express** no **Portainer** utilizando a imagem compilada automaticamente pelo **GitHub Actions**.

---

## ⚡ 1. Como Funciona a Compilação Automática

Toda vez que você faz um `git push` para a branch `main` no GitHub:
1. O **GitHub Actions** compila a imagem Docker otimizada.
2. A imagem é publicada no **GitHub Container Registry (GHCR)** no endereço:
   `ghcr.io/cristhian-sancore/graficarapida:latest`
3. A imagem fica pública e pronta para ser baixada pelo **Portainer**.

---

## 📋 2. Docker Compose para Colar no Portainer (Stack)

No seu **Portainer**, vá em **Stacks** ➔ **Add stack** ➔ **Web editor** e cole o seguinte código YAML:

```yaml
version: '3.8'

services:
  grafica-express:
    image: ghcr.io/cristhian-sancore/graficarapida:latest
    container_name: grafica_rapida_portainer
    restart: always
    ports:
      - "8050:8050"
    environment:
      - PORT=8050
      - FLASK_ENV=production
    volumes:
      - grafica_db_data:/app/data
      - grafica_uploads_data:/app/static/uploads

volumes:
  grafica_db_data:
    driver: local
  grafica_uploads_data:
    driver: local
```

---

## 🚀 3. Passos no Portainer

1. Acesse o **Portainer**.
2. Clique no seu ambiente (**Primary / Local**).
3. Vá no menu lateral **Stacks** e clique no botão **+ Add stack**.
4. Defina o nome da stack: `grafica-express`.
5. Cole a configuração YAML acima.
6. Clique no botão **Deploy the stack**.
7. Pronto! A aplicação estará rodando em: **`http://SEU_SERVIDOR_IP:8050`**.
