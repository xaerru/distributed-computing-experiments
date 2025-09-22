FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy edge server files
COPY server.py .

# Create directories for edge server data
RUN mkdir -p es0 es1 es2 es3 es4

# Expose edge server ports (8001-8005)
EXPOSE 8001 8002 8003 8004 8005

# The CMD will be overridden by docker-compose to specify the node_id
CMD ["python", "server.py", "0"]