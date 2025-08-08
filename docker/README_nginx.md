# Nginx Configuration (Optional)

This file contains the nginx configuration that was removed from the main template to keep it simple for internal testing.

If you want to add nginx back as a reverse proxy for production deployment, you can:

1. **Restore this file:**
```bash
mv docker/nginx.conf.backup docker/nginx.conf
```

2. **Add nginx service back to docker-compose.yml:**
```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./docker/nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - app
    restart: unless-stopped
    networks:
      - rag-network
```

3. **Update app service ports in docker-compose.yml:**
```yaml
  app:
    # Remove or comment out the ports section since nginx will handle routing
    # ports:
    #   - "8000:8000"
```

4. **Access the application:**
- With nginx: http://localhost (port 80)
- Direct access: http://localhost:8000

## Benefits of using nginx:
- Load balancing for multiple app instances
- SSL termination
- Static file serving
- Request rate limiting
- Better security headers
- Production-grade web server

For internal testing and development, direct access to port 8000 is simpler and sufficient.
