FROM python:3.11-slim

# Install uv
RUN pip install uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock README.md ./
COPY py/ ./py/

# Install dependencies
RUN uv sync --frozen --no-dev

# Create directory for hippo data
RUN mkdir -p /data

# Expose port for MCP server (if needed for HTTP transport)
EXPOSE 8080

# Default command - can be overridden
CMD ["uv", "run", "python", "-m", "py.hippo.server", "--hippo-file", "/data/hippo.json"]
