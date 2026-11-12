# ---------- frontend build ----------
FROM node:22-bookworm-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------- app (docker compose up) ----------
FROM python:3.11-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
COPY --from=frontend-build /src/frontend/dist /app/static
ENV STATIC_DIR=/app/static DB_PATH=/data/mission_control.db PATH="/app/backend/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

# ---------- tests (docker compose run --rm test) ----------
# Python + Node in one image so one command runs both suites. Runs with network_mode: none.
FROM node:22-bookworm-slim AS test
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_LINK_MODE=copy
WORKDIR /work/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv python install 3.11 && uv sync --frozen --no-install-project
WORKDIR /work/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY backend /work/backend
COPY frontend /work/frontend
COPY scripts/run-tests.sh /work/run-tests.sh
WORKDIR /work
CMD ["sh", "/work/run-tests.sh"]
