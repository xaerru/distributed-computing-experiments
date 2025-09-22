FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy server files
COPY canonical_server.py .
COPY images/ ./images/

# Expose the canonical server port
EXPOSE 9000

# Run the canonical server
CMD ["python", "canonical_server.py"]