# 🚢 Guia de Implantação no Portainer (GitHub Actions + GHCR)

Este documento ensina como implantar a **Gráfica Rápida Express** no **Portainer** utilizando a imagem compilada automaticamente pelo **GitHub Actions** com persistência de banco de dados SQLite.

---

## ⚡ 1. Como Funciona a Compilação Automática

Toda vez que você faz um `git push` para a branch `main` no GitHub:
1. O **GitHub Actions** compila a imagem Docker otimizada.
2. A imagem é publicada no **GitHub Container Registry (GHCR)** no endereço:
   `ghcr.io/cristhian-sancore/graficarapida:latest`
3. A imagem fica pública e pronta para ser baixada pelo **Portainer**.

---

## 📋 2. Docker Compose Atualizado para Colar no Portainer (Stack)

No seu **Portainer**, vá em **Stacks** ➔ **Add stack** (ou selecione a stack existente e clique em **Editor**) e cole a configuração abaixo:

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
      - DB_PATH=/app/data/grafica.db
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

## 🚀 3. O que esta configuração garante:

1. **Persistência Total do Banco de Dados**: A variável `DB_PATH=/app/data/grafica.db` faz a aplicação gravar e ler as informações relativas a clientes, pedidos e configurações dentro do volume Docker permanente `grafica_db_data`.
2. **Sem perda de dados entre reinicializações**: Mesmo ao reiniciar o servidor ou reinstalar a Stack, os dados dos clientes e do painel admin continuam salvos e protegidos.
3. **Suporte Inteligente a WhatsApp**: Envio automático de mensagens com verificação de 8 e 9 dígitos para telefones do Brasil.
