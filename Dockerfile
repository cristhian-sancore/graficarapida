# Imagem base Python slim otimizada
FROM python:3.11-slim

# Evita geração de arquivos .pyc e força output imediato sem buffer
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8050

WORKDIR /app

# Instalar dependências do sistema necessárias
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivo de dependências e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código-fonte da aplicação
COPY . .

# Criar pasta estática de uploads se não existir
RUN mkdir -p /app/static/uploads

# Expor a porta da aplicação
EXPOSE 8050

# Executar aplicação via Gunicorn em produção
CMD ["gunicorn", "--bind", "0.0.0.0:8050", "--workers", "2", "--timeout", "120", "app:app"]
