"""
Load balancer for the CDN demo.
Usage: python load_balancer.py
Hardcoded config:
  lb_port = 8000
  edge_base_port = 8001
  num_edges = 5
  host = '127.0.0.1'
The LB performs round-robin over healthy edge servers.
Health checks are done via 'heartbeat' RPC every 5 seconds.
Clients should connect to the LB at port 8000 instead of directly to edges.
"""
import socket, json, struct, threading, time

HOST = '127.0.0.1'
LB_PORT = 8000
EDGE_BASE_PORT = 8001
NUM_EDGES = 5
HEALTH_CHECK_INTERVAL = 5.0
HEARTBEAT_TIMEOUT = 1.0

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

class LoadBalancer:
    def __init__(self):
        self.healthy = [True] * NUM_EDGES
        self.current_index = 0
        self.lock = threading.Lock()
        self.alive = True
        print(f"Load Balancer initialized on port {LB_PORT}")

    def start(self):
        threading.Thread(target=self._start_listener, daemon=True).start()
        threading.Thread(target=self.health_check, daemon=True).start()
        try:
            while self.alive:
                time.sleep(1)
        except KeyboardInterrupt:
            self.alive = False
            print("Load Balancer shutting down")

    def _start_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, LB_PORT))
            s.listen()
            print(f"Load Balancer listening on {HOST}:{LB_PORT}")
            while self.alive:
                try:
                    conn, addr = s.accept()
                    print(f"Load Balancer: Accepted connection from {addr}")
                    threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
                except Exception as e:
                    print(f"Load Balancer: Error accepting connection: {e}")

    def choose_edge(self) -> int:
        with self.lock:
            healthy_indices = [i for i in range(NUM_EDGES) if self.healthy[i]]
            if not healthy_indices:
                raise Exception("No healthy edge servers available")
            idx = self.current_index % len(healthy_indices)
            self.current_index += 1
            port = EDGE_BASE_PORT + healthy_indices[idx]
            print(f"Load Balancer: Chosen edge server at port {port}")
            return port

    def handle_client(self, client_conn: socket.socket):
        try:
            edge_port = self.choose_edge()
            print(f"Load Balancer: Forwarding request to edge at {edge_port}")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as edge_sock:
                edge_sock.connect((HOST, edge_port))
                print(f"Load Balancer: Connected to edge at {edge_port}")
                # Receive full request from client
                size_data = recv_exact(client_conn, 8)
                (req_len,) = struct.unpack("Q", size_data)
                req_json = recv_exact(client_conn, req_len)
                request_data = json.loads(req_json.decode())
                print(f"Load Balancer: Received request: {request_data}")
                # Forward to edge
                edge_sock.sendall(size_data)
                edge_sock.sendall(req_json)
                edge_sock.shutdown(socket.SHUT_WR)
                print(f"Load Balancer: Forwarded request to edge {edge_port}")
                # Forward response from edge to client
                while True:
                    data = edge_sock.recv(4096)
                    if not data:
                        break
                    client_conn.sendall(data)
                print(f"Load Balancer: Forwarded response from edge {edge_port} to client")
        except Exception as e:
            print(f"Load Balancer: Error handling client: {e}")
            # Send error response to client
            try:
                clock_data = struct.pack("Q", 0)
                err_msg = json.dumps({"error": str(e)}).encode()
                size_data = struct.pack("Q", len(err_msg))
                client_conn.sendall(clock_data)
                client_conn.sendall(size_data)
                client_conn.sendall(err_msg)
                print(f"Load Balancer: Sent error response to client")
            except Exception as inner_e:
                print(f"Load Balancer: Error sending error response: {inner_e}")
        finally:
            client_conn.close()
            print("Load Balancer: Closed client connection")

    def health_check(self):
        while self.alive:
            for i in range(NUM_EDGES):
                port = EDGE_BASE_PORT + i
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(HEARTBEAT_TIMEOUT)
                        s.connect((HOST, port))
                        req = json.dumps({"function": "heartbeat", "args": [], "clock": 0}).encode()
                        s.sendall(struct.pack("Q", len(req)))
                        s.sendall(req)
                        recv_exact(s, 8)  # clock
                    with self.lock:
                        self.healthy[i] = True
                    print(f"Load Balancer: Health check passed for edge {i} at port {port}")
                except Exception as e:
                    with self.lock:
                        self.healthy[i] = False
                    print(f"Load Balancer: Health check failed for edge {i} at port {port}: {e}")
            print(f"Load Balancer: Current healthy edges: {self.healthy}")
            time.sleep(HEALTH_CHECK_INTERVAL)

if __name__ == "__main__":
    lb = LoadBalancer()
    lb.start()
