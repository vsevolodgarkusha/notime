# Stage 1: Build dependencies
FROM python:3.14.2-slim AS builder

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
COPY main.py .

# Command to run the application
CMD ["uv", "run", "python", "main.py"]
