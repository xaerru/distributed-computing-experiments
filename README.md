# Distributed Computing Assignment - Docker Setup

This repository demonstrates a distributed computing system with one canonical server and three edge servers running in Docker containers.

## Architecture

- **Canonical Server**: Stores the original images and serves them to edge servers
- **Edge Servers (3)**: Cache images and serve client requests, implement leader election using the Bully algorithm
- **Client**: Load balances requests across edge servers based on image ID

## Prerequisites

- Docker Desktop installed and running
- Docker Compose available

## Quick Start

### Option 1: Using Start Scripts (Recommended)

**Windows:**
```cmd
start-system.bat
```

**Linux/Mac:**
```bash
chmod +x start-system.sh
./start-system.sh
```

### Option 2: Manual Docker Compose

1. **Start the distributed system:**
   ```bash
   docker-compose up -d canonical-server edge-server-1 edge-server-2 edge-server-3
   ```

2. **Run the client (interactive):**
   ```bash
   docker-compose run --rm client
   ```

3. **Stop the system:**
   ```bash
   docker-compose down
   ```

## Services

| Service | Container Name | Port | Description |
|---------|---------------|------|-------------|
| Canonical Server | canonical-server | 9000 | Stores original images |
| Edge Server 1 | edge-server-1 | 8001 | Edge cache node 1 |
| Edge Server 2 | edge-server-2 | 8002 | Edge cache node 2 |
| Edge Server 3 | edge-server-3 | 8003 | Edge cache node 3 |

## Testing the System

1. **Start the system** using one of the methods above
2. **Run the client**:
   ```bash
   docker-compose run --rm client
   ```
3. **Test operations**:
   - Choose option 1 (get_image) or 2 (get_image_size)
   - Enter an image ID (e.g., 123, 456, etc.)
   - The client will automatically load balance to the appropriate edge server

## Monitoring

**View logs of all services:**
```bash
docker-compose logs -f
```

**View logs of specific service:**
```bash
docker-compose logs -f canonical-server
docker-compose logs -f edge-server-1
docker-compose logs -f edge-server-2
docker-compose logs -f edge-server-3
```

**Check service status:**
```bash
docker-compose ps
```

## Key Features Demonstrated

1. **Containerization**: Each server runs in its own Docker container
2. **Service Discovery**: Containers communicate using Docker service names
3. **Load Balancing**: Client distributes requests based on image ID modulo 3
4. **Leader Election**: Edge servers implement Bully algorithm for coordination
5. **Caching**: Edge servers cache images from the canonical server
6. **Replication**: Leader edge server replicates images to followers

## Network Architecture

- All containers run on a custom Docker network (`distributed-net`)
- Containers communicate using service names (e.g., `canonical-server`, `edge-server-1`)
- Ports are exposed to the host for external access

## Troubleshooting

**If containers fail to start:**
1. Check Docker Desktop is running
2. Ensure ports 8001-8003 and 9000 are not in use
3. Run `docker-compose down` and try again

**If services can't communicate:**
1. Check the logs: `docker-compose logs`
2. Verify containers are on the same network: `docker network ls`
3. Test connectivity: `docker-compose exec edge-server-1 ping canonical-server`

**To completely reset:**
```bash
docker-compose down
docker system prune -f
docker-compose up -d --build
```

## File Structure

```
distributed-computing-experiments/
├── server/
│   ├── Dockerfile
│   ├── canonical_server.py
│   └── images/
├── edge_server/
│   ├── Dockerfile
│   └── server.py
├── client/
│   ├── Dockerfile
│   ├── client.py (original)
│   └── client_docker.py (Docker version)
├── docker-compose.yml
├── start-system.sh
├── start-system.bat
└── README.md
```

## Assignment Demonstration

This setup perfectly demonstrates:
- **Distributed System**: Multiple independent nodes working together
- **Containerization**: Each component runs in isolation
- **Service Communication**: Inter-container networking and RPC
- **Fault Tolerance**: Leader election and failover mechanisms
- **Load Distribution**: Client-side load balancing
- **Data Replication**: Image caching and synchronization

The system shows real distributed computing concepts including node coordination, service discovery, and data consistency in a containerized environment.
