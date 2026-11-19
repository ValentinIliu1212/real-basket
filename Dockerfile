# RealBasket - Streamlit dashboard + chat agent (the agent starts the MCP server `realbasket` as a stdio subprocess
# inside the same container). Build: docker build -t realbasket .   Run: see README "Docker".
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

RUN pip install "poetry>=2.0,<3.0"

# dependencies first (cached layer), then the code; the project is installed from /app so that
# core.settings.PROJECT_ROOT = /app (reference PDFs, data_store and .env are resolved against it)
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root
COPY src ./src
COPY reports/real-data ./reports/real-data
RUN poetry install --only main

# non-root user; data_store (method-note index) must be writable -> mount a volume to keep it
RUN useradd --create-home --uid 1000 realbasket \
    && mkdir -p /app/data_store /app/reports \
    && chown -R realbasket:realbasket /app/data_store /app/reports
USER realbasket

EXPOSE 8501 8001

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=4)"

# LLM settings are passed at runtime (--env-file .env / docker compose env_file), never baked into the image
CMD ["streamlit", "run", "src/real_basket/ui/app.py"]
