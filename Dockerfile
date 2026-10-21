FROM python:3.11-slim

# Evita geração de .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    ENVIRONMENT=production

WORKDIR /app

# Instala dependências do sistema necessárias se houver
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código-fonte da aplicação
COPY api.py database.py engine.py ./
COPY scripts/ ./scripts/ 2>/dev/null || true

# Cria usuário não-root para segurança em produção
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Healthcheck interno do container
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
