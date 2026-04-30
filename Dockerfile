# Pakistan News Scraper — VPS-ready container
#
# Build:  docker build -t pk-scraper .
# Run:    docker run -d --name pk-scraper \
#               -v "$PWD/data:/app/data" \
#               -v "$PWD/exports:/app/exports" \
#               -e SCRAPER_CONTACT_EMAIL=you@example.com \
#               --restart unless-stopped \
#               pk-scraper
# Logs:   docker logs -f pk-scraper
# Stop:   docker stop pk-scraper

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    URDU_ONLY=true

# Playwright browser deps (Chromium needs these even in headless mode)
RUN apt-get update && apt-get install -y --no-install-recommends \
        sqlite3 ca-certificates curl tini procps \
        libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
        libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 \
        libasound2 libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && playwright install chromium --with-deps 2>/dev/null || playwright install chromium

COPY . .

# Persistent volumes for the SQLite DB and CSV exports
RUN mkdir -p /app/data /app/exports /app/httpcache
VOLUME ["/app/data", "/app/exports"]

# tini reaps zombie children spawned by keep_alive.sh
ENTRYPOINT ["tini", "--"]
CMD ["bash", "scripts/keep_alive.sh"]
