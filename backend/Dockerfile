# FastAPI backend. Build:  docker build -t sgw-backend .
# Run (key passed at runtime, never baked into the image):
#   docker run -p 8000:8000 --env-file src/backend/.env sgw-backend
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# LightGBM needs the OpenMP runtime
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# dependencies first, so code changes don't reinstall them
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --locked --no-dev --no-install-project

# code and data (processed assets.json and the trained model are committed, nothing to generate)
COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
# 0.0.0.0 so the port is reachable from outside the container (uv run backend binds 127.0.0.1)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
