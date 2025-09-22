"""
Edge server for the CDN-like demo.
Usage: python server.py <node_id>
node_id: 0..4 (we create 5 edge servers on consecutive ports)
Hardcoded config:
  edge_base_port = 8001 -> ports 8001..8005
  canonical server at 127.0.0.1:9000
RPC format:
- Client sends: <8-byte length><JSON request bytes>
  JSON: {"function": "                    s.sendall(msg)
                    # read ack
                    recv_exact(s, 8)
                    size_data = s.recv(8)
                    if size_data:
                        (size,) = struct.unpack("Q", size_data)
                        payload = recv_exact(s, size) if size>0 else b""
                print(f"Edge {self.node_id}: instruct replication to {peer['host']}:{peer['port']} completed") 
            except Exception as e:
                print(f"Edge {self.node_id}: replication to {peer['host']}:{peer['port']} failed -> {e}")s": [...], "clock": <int>}
- Server responds: <8-byte clock><...> then function-specific payload
Supported RPC functions (from clients or inter-edge):
- get_image [id]
- get_image_size [id]
- replicate [id, leader_host, leader_port]   # follower will fetch image from leader
- notify_cached [id]  # follower notifies leader it cached an image
- election [candidate_id]
- election_ok []
- coordinator [leader_id]
- heartbeat []
"""
import socket, json, struct, os, sys, threading, time

HOST = '0.0.0.0'  # Listen on all interfaces for Docker
EDGE_BASE_PORT = 8001
NUM_EDGES = 3  # Only 3 edge servers for this assignment
CANONICAL_HOST = 'canonical-server'  # Docker service name
CANONICAL_PORT = 9000

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

def peer_rpc_call(peer_host: str, peer_port: int, function: str, args: list, timeout=5):
    """Sends RPC to peer and returns raw response (clock, maybe size, maybe data)"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((peer_host, peer_port))
            request = json.dumps({"function": function, "args": args, "clock": 0}).encode()
            s.sendall(struct.pack("Q", len(request)))
            s.sendall(request)
            # Read response clock
            resp_clock_data = recv_exact(s, 8)
            (resp_clock,) = struct.unpack("Q", resp_clock_data)
            if function in ("get_image",):
                size_data = recv_exact(s, 8)
                (size,) = struct.unpack("Q", size_data)
                image = recv_exact(s, size)
                return resp_clock, size, image
            elif function in ("get_image_size",):
                size_data = recv_exact(s, 8)
                (size,) = struct.unpack("Q", size_data)
                return resp_clock, size, None
            else:
                # generic: may be coordinator/election replies with no payload
                try:
                    # attempt to read a following size and payload (some functions send nothing)
                    size_data = s.recv(8)
                    if not size_data:
                        return resp_clock, None, None
                    (size,) = struct.unpack("Q", size_data)
                    payload = recv_exact(s, size) if size > 0 else b""
                    return resp_clock, size, payload
                except Exception:
                    return resp_clock, None, None
    except Exception as e:
        # print(f"peer_rpc_call failed to {peer_host}:{peer_port} -> {e}")
        raise

class EdgeServer:
    def __init__(self, node_id:int):
        self.node_id = node_id
        self.port = EDGE_BASE_PORT + node_id
        self.es_dir = os.path.join(os.getcwd(), f"es{node_id}")
        os.makedirs(self.es_dir, exist_ok=True)
        # Create peer mappings for Docker networking
        self.peers = []
        for i in range(NUM_EDGES):
            if i != node_id:
                self.peers.append({
                    'id': i,
                    'host': f'edge-server-{i}',
                    'port': EDGE_BASE_PORT + i
                })
        self.leader_id = None
        self.leader_lock = threading.Lock()
        self.alive = True
        # For heartbeat monitoring
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 2.0
        self.heartbeat_fail_threshold = 6.0  # if no heartbeat/ping for this many seconds -> election
        print(f"Edge {node_id} running on port {self.port}, data dir: {self.es_dir}")
        peer_list = [f"{p['host']}:{p['port']}" for p in self.peers]
        print(f"Peers: {peer_list}")

    def start(self):
        threading.Thread(target=self._start_listener, daemon=True).start()
        time.sleep(0.5)
        # Start election at startup
        threading.Thread(target=self.run_election, daemon=True).start()
        # Start heartbeat monitoring thread
        threading.Thread(target=self.heartbeat_monitor, daemon=True).start()
        # Keep main thread alive
        try:
            while self.alive:
                time.sleep(1)
        except KeyboardInterrupt:
            self.alive = False

    def _start_listener(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((HOST, self.port))
            s.listen()
            while self.alive:
                try:
                    conn, _ = s.accept()
                    threading.Thread(target=self.handle_client, args=(conn,), daemon=True).start()
                except Exception:
                    pass

    def handle_client(self, conn: socket.socket):
        with conn:
            try:
                size_data = recv_exact(conn, 8)
                (size,) = struct.unpack("Q", size_data)
                request = recv_exact(conn, size).decode()
                data = json.loads(request)
                func = data.get("function")
                args = data.get("args", [])
                # Simple logging
                print(f"Edge {self.node_id}({self.port}): Received RPC {func} {args}")
                # respond with clock 0 always for simplicity
                conn.sendall(struct.pack("Q", 0))
                if func == "get_image":
                    img_id = args[0]
                    local_path = os.path.join(self.es_dir, f"image{img_id}.jpg")
                    if os.path.exists(local_path):
                        filesize = os.path.getsize(local_path)
                        conn.sendall(struct.pack("Q", filesize))
                        with open(local_path, "rb") as f:
                            conn.sendfile(f)
                        print(f"Edge {self.node_id}: served image{img_id}.jpg from local cache") 
                    else:
                        # Cache miss: fetch from canonical
                        print(f"Edge {self.node_id}: cache miss for image{img_id}, fetching from canonical...")
                        try:
                            _, size, image = peer_rpc_call(CANONICAL_HOST, CANONICAL_PORT, "get_image", [img_id])
                            assert(image != None)
                            # store locally
                            with open(local_path, "wb") as f:
                                f.write(image)
                            conn.sendall(struct.pack("Q", size))
                            conn.sendall(image)
                            print(f"Edge {self.node_id}: cached image{img_id}.jpg locally ({size} bytes)" )
                            # Post-cache actions:
                            if self.is_leader():
                                # leader will ensure replication by instructing peers to fetch from leader
                                threading.Thread(target=self.replicate_to_peers, args=(img_id,), daemon=True).start()
                            else:
                                # notify leader to replicate
                                self.notify_leader_cached(img_id)
                        except Exception as e:
                            err = json.dumps({"error": str(e)}).encode()
                            conn.sendall(struct.pack("Q", len(err)))
                            conn.sendall(err)
                elif func == "get_image_size":
                    img_id = args[0]
                    local_path = os.path.join(self.es_dir, f"image{img_id}.jpg")
                    if os.path.exists(local_path):
                        filesize = os.path.getsize(local_path)
                        conn.sendall(struct.pack("Q", filesize))
                    else:
                        # Ask canonical for size and return
                        try:
                            _, size, _ = peer_rpc_call(CANONICAL_HOST, CANONICAL_PORT, "get_image_size", [img_id])
                            conn.sendall(struct.pack("Q", size))
                        except Exception as e:
                            err = json.dumps({"error": str(e)}).encode()
                            conn.sendall(struct.pack("Q", len(err)))
                            conn.sendall(err)
                elif func == "replicate":
                    # Instruction from leader: fetch image from leader_host:leader_port
                    img_id = args[0]
                    leader_host = args[1]
                    leader_port = args[2]
                    print(f"Edge {self.node_id}: replicate request -> pull image{img_id} from leader {leader_port}")
                    try:
                        _, size, image = peer_rpc_call(leader_host, leader_port, "get_image", [img_id])
                        assert(image != None)
                        local_path = os.path.join(self.es_dir, f"image{img_id}.jpg")
                        with open(local_path, "wb") as f:
                            f.write(image)
                        # send acknowledgement payload (optional)
                        ack = json.dumps({"ok": True}).encode()
                        conn.sendall(struct.pack("Q", len(ack)))
                        conn.sendall(ack)
                        print(f"Edge {self.node_id}: replicated image{img_id} from leader {leader_port}")
                    except Exception as e:
                        err = json.dumps({"error": str(e)}).encode()
                        conn.sendall(struct.pack("Q", len(err)))
                        conn.sendall(err)
                elif func == "notify_cached":
                    img_id = args[0]
                    print(f"Edge {self.node_id}: received notify_cached for image{img_id}") 
                    # Only leader reacts to this by initiating replication to other peers
                    if self.is_leader():
                        threading.Thread(target=self.replicate_to_peers, args=(img_id,), daemon=True).start()
                    conn.sendall(struct.pack("Q", 0))
                elif func == "election":
                    cand = args[0]
                    # If we receive election from lower id, reply election_ok and start our own election if higher
                    # Reply: send some small payload
                    ok = json.dumps({"ok": True}).encode()
                    conn.sendall(struct.pack("Q", 0))
                    conn.sendall(struct.pack("Q", len(ok)))
                    conn.sendall(ok)
                    # start our election if our id is higher than candidate
                    if self.node_id > cand:
                        threading.Thread(target=self.run_election, daemon=True).start()
                elif func == "coordinator":
                    leader = args[0]
                    with self.leader_lock:
                        self.leader_id = leader
                    print(f"Edge {self.node_id}: new coordinator is {leader}")
                    conn.sendall(struct.pack("Q", 0))
                elif func == "heartbeat":
                    # simple ping reply
                    with self.leader_lock:
                        self.last_heartbeat = time.time()
                    conn.sendall(struct.pack("Q", 0))
                else:
                    # unknown function
                    err = json.dumps({"error": f"Unknown function {func}"}).encode()
                    conn.sendall(struct.pack("Q", len(err)))
                    conn.sendall(err)
            except Exception as e:
                # best-effort error send
                try:
                    err = json.dumps({"error": str(e)}).encode()
                    conn.sendall(struct.pack("Q", 0))
                    conn.sendall(struct.pack("Q", len(err)))
                    conn.sendall(err)
                except Exception:
                    pass

    def is_leader(self):
        with self.leader_lock:
            return (self.leader_id is not None and self.leader_id == self.node_id)

    def run_election(self):
        print(f"Edge {self.node_id}: starting election..." )
        # Bully algorithm: contact all nodes with higher IDs
        higher = [i for i in range(NUM_EDGES) if i > self.node_id]
        got_ok = False
        for hid in higher:
            host = f'edge-server-{hid}'
            port = EDGE_BASE_PORT + hid
            try:
                # send election message
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect((host, port))
                    req = json.dumps({"function": "election", "args": [self.node_id], "clock": 0}).encode()
                    s.sendall(struct.pack("Q", len(req)))
                    s.sendall(req)
                    # read response
                    resp_clock = recv_exact(s, 8)
                    size_data = s.recv(8)
                    if size_data:
                        (size,) = struct.unpack("Q", size_data)
                        payload = recv_exact(s, size) if size>0 else b""
                    got_ok = True
                    print(f"Edge {self.node_id}: got election_ok from {hid}")
            except Exception:
                # no response from that higher node
                pass
        if not got_ok:
            # we are the highest alive -> announce coordinator
            print(f"Edge {self.node_id}: no higher node replied, declaring self coordinator" )
            for i in range(NUM_EDGES):
                if i == self.node_id: continue
                host = f'edge-server-{i}'
                port = EDGE_BASE_PORT + i
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(2)
                        s.connect((host, port))
                        msg = json.dumps({"function": "coordinator", "args": [self.node_id], "clock": 0}).encode()
                        s.sendall(struct.pack("Q", len(msg)))
                        s.sendall(msg)
                        # read optional reply
                        recv_exact(s, 8)
                except Exception:
                    pass
            with self.leader_lock:
                self.leader_id = self.node_id
            print(f"Edge {self.node_id}: I am the leader now") 
        else:
            # wait for coordinator announcement (simple strategy: poll leader field periodically)
            # If no coordinator announced in some time, try again
            wait_until = time.time() + 5
            while time.time() < wait_until:
                with self.leader_lock:
                    if self.leader_id is not None:
                        return
                time.sleep(0.5)
            # if still no coordinator, restart election
            threading.Thread(target=self.run_election, daemon=True).start()

    def replicate_to_peers(self, img_id:int):
        """Leader instructs other peers to pull the image from the leader (leader-initiated replication)."""
        print(f"Edge {self.node_id}: replicating image{img_id} to peers..." )
        # leader info - use container hostname
        leader_host = f'edge-server-{self.node_id}'
        leader_port = self.port
        for peer in self.peers:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(4)
                    s.connect((peer['host'], peer['port']))
                    msg = json.dumps({"function": "replicate", "args": [img_id, leader_host, leader_port], "clock": 0}).encode()
                    s.sendall(struct.pack("Q", len(msg)))
                    s.sendall(msg)
                    # read ack
                    recv_exact(s, 8)
                    size_data = s.recv(8)
                    if size_data:
                        (size,) = struct.unpack("Q", size_data)
                        payload = recv_exact(s, size) if size>0 else b""
                print(f"Edge {self.node_id}: instruct replication to {peer['host']}:{peer['port']} completed") 
            except Exception as e:
                print(f"Edge {self.node_id}: replication to {peer['host']}:{peer['port']} failed -> {e}") 

    def notify_leader_cached(self, img_id:int):
        with self.leader_lock:
            leader = self.leader_id
        if leader is None:
            print(f"Edge {self.node_id}: no leader known, starting election to ensure replication" )
            threading.Thread(target=self.run_election, daemon=True).start()
            return
        leader_port = EDGE_BASE_PORT + leader
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3)
                s.connect((HOST, leader_port))
                msg = json.dumps({"function": "notify_cached", "args": [img_id], "clock": 0}).encode()
                s.sendall(struct.pack("Q", len(msg)))
                s.sendall(msg)
                recv_exact(s, 8)  # read ack clock
            print(f"Edge {self.node_id}: notified leader {leader} about cached image{img_id}") 
        except Exception as e:
            print(f"Edge {self.node_id}: failed to notify leader -> {e}") 
            # if notify fails, maybe leader is down -> trigger election
            threading.Thread(target=self.run_election, daemon=True).start()

    def heartbeat_monitor(self):
        # Followers ping leader periodically to detect liveness. If leader not responding, trigger election.
        while self.alive:
            time.sleep(self.heartbeat_interval)
            with self.leader_lock:
                leader = self.leader_id
            if leader is None or leader == self.node_id:
                # if I'm leader, update heartbeat timestamp
                if leader == self.node_id:
                    self.last_heartbeat = time.time()
                continue
            leader_port = EDGE_BASE_PORT + leader
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect((HOST, leader_port))
                    msg = json.dumps({"function": "heartbeat", "args": [], "clock": 0}).encode()
                    s.sendall(struct.pack("Q", len(msg)))
                    s.sendall(msg)
                    recv_exact(s, 8)  # read reply clock
                    # got heartbeat ack -> update timestamp
                    self.last_heartbeat = time.time()
            except Exception:
                # check elapsed since last heartbeat
                if time.time() - self.last_heartbeat > self.heartbeat_fail_threshold:
                    print(f"Edge {self.node_id}: leader heartbeat lost; starting election" )
                    threading.Thread(target=self.run_election, daemon=True).start()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: python server.py <node_id (0..{NUM_EDGES-1})>")
        sys.exit(1)
    node_id = int(sys.argv[1])
    if node_id < 0 or node_id >= NUM_EDGES:
        print(f"node_id must be 0..{NUM_EDGES-1}")
        sys.exit(1)
    server = EdgeServer(node_id)
    server.start()
