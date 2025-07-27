# Docker Usage for Hippo

## Quick Start with Podman/Docker

### Build the image:
```bash
podman build -t hippo-server .
# or: docker build -t hippo-server .
```

### Run with persistent storage:
```bash
# Create data directory
mkdir -p ./data

# Run the server
podman run -d \
  --name hippo \
  -p 8080:8080 \
  -v ./data:/data:Z \
  hippo-server

# or: docker run -d --name hippo -p 8080:8080 -v ./data:/data hippo-server
```

### Using docker-compose/podman-compose:
```bash
podman-compose up -d
# or: docker-compose up -d
```

## Configuration

### Custom hippo file location:
```bash
podman run -d \
  --name hippo \
  -p 8080:8080 \
  -v /path/to/your/data:/data:Z \
  hippo-server \
  uv run python -m py.hippo.server --hippo-file /data/my-hippo.json
```

### Environment variables:
```bash
podman run -d \
  --name hippo \
  -p 8080:8080 \
  -v ./data:/data:Z \
  -e PYTHONUNBUFFERED=1 \
  hippo-server
```

## Development

### Run with source code mounted (for development):
```bash
podman run -it --rm \
  -p 8080:8080 \
  -v ./data:/data:Z \
  -v ./py:/app/py:Z \
  hippo-server
```

### Interactive shell in container:
```bash
podman run -it --rm \
  -v ./data:/data:Z \
  hippo-server \
  /bin/bash
```

## Logs and Debugging

### View logs:
```bash
podman logs hippo
# or: docker logs hippo
```

### Follow logs:
```bash
podman logs -f hippo
# or: docker logs -f hippo
```

## Notes

- The server runs on port 8080 inside the container
- Data is persisted in the `/data` volume mount
- Default hippo file is `/data/hippo.json`
- The `:Z` flag in volume mounts is for SELinux systems (like Fedora/RHEL)
