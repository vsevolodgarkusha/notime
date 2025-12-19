# Stage 1: Build dependencies
FROM python:3.14.2-slim AS builder

# Install build essentials for compiling packages like psycopg2
RUN apt-get update && apt-get install -y build-essential libpq-dev

# Install uv by copying it from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency definition
COPY pyproject.toml .

# Create virtual environment and install dependencies
RUN uv sync



# Stage 2: Final image
FROM python:3.14.2-slim

# Install uv by copying it from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the virtual environment with dependencies from the builder stage
COPY --from=builder ./.venv ./.venv

# Set the working directory, which will contain the app code and the venv
WORKDIR /app

# Set up the PATH to include the venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application code
COPY app/ ./app

# Command to run the application
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
