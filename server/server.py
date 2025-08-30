import socket, json, os, struct, concurrent.futures, sys

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

def get_image_path(id: int):
    return f"server/images/image{id}.jpg"

def get_image_size(id: int):
    image_path = get_image_path(id)
    filesize = os.path.getsize(image_path)
    return filesize

def get_image(id: int):
    image_path = get_image_path(id)
    filesize = os.path.getsize(image_path)
    f = open(image_path, "rb")
    return filesize, f

def is_local_image(port: int, id: int) -> bool:
    # For demo: Even IDs local to port % 2 == 0 (e.g., 8080), odd to 8081
    return (id % 2) == (port % 2)

def peer_rpc_call(peer_host: str, peer_port: int, function: str, args: list, clock: int):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((peer_host, peer_port))
        request = json.dumps({"function": function, "args": args, "clock": clock}).encode()
        s.sendall(struct.pack("Q", len(request)))
        s.sendall(request)

        # Receive response clock
        resp_clock_data = recv_exact(s, 8)
        (resp_clock,) = struct.unpack("Q", resp_clock_data)

        if function == "get_image":
            # Receive size
            size_data = recv_exact(s, 8)
            (size,) = struct.unpack("Q", size_data)
            # Receive image
            image = recv_exact(s, size)
            return resp_clock, size, image
        elif function == "get_image_size":
            # Receive size
            size_data = recv_exact(s, 8)
            (size,) = struct.unpack("Q", size_data)
            return resp_clock, size, None
        else:
            raise ValueError("Unknown function")

def handle_request(conn: socket.socket, request: str, port: int, peer_host: str, peer_port: int, logical_clock: list):
    try:
        data = json.loads(request)
        func_name = data["function"]
        args = data["args"]

        # Increment for processing
        logical_clock[0] += 1
        print(f"Server {port}: Processing request at clock {logical_clock[0]}")

        id = args[0]
        if func_name in ["get_image", "get_image_size"] and not is_local_image(port, id):
            print(f"Server {port}: Image {id} not local, forwarding to peer {peer_port} at clock {logical_clock[0]}")
            # Forward to peer: increment for send
            logical_clock[0] += 1
            if func_name == "get_image":
                resp_clock, size, image = peer_rpc_call(peer_host, peer_port, func_name, args, logical_clock[0])
                if image is not None:
                    # Update clock on receive
                    logical_clock[0] = max(logical_clock[0], resp_clock) + 1
                    print(f"Server {port}: Received from peer at updated clock {logical_clock[0]}")
                    # Increment for forwarding send
                    logical_clock[0] += 1
                    print(f"Server {port}: Sending to client at clock {logical_clock[0]}")
                    # Send clock, size, image
                    conn.sendall(struct.pack("Q", logical_clock[0]))
                    conn.sendall(struct.pack("Q", size))
                    conn.sendall(image)
                else:
                    raise RuntimeError("Peer didn't return image")
            elif func_name == "get_image_size":
                resp_clock, size, _ = peer_rpc_call(peer_host, peer_port, func_name, args, logical_clock[0])
                # Update clock on receive
                logical_clock[0] = max(logical_clock[0], resp_clock) + 1
                print(f"Server {port}: Received from peer at updated clock {logical_clock[0]}")
                # Increment for forwarding send
                logical_clock[0] += 1
                print(f"Server {port}: Sending to client at clock {logical_clock[0]}")
                # Send clock, size
                conn.sendall(struct.pack("Q", logical_clock[0]))
                conn.sendall(struct.pack("Q", size))
        else:
            if func_name == "get_image":
                filesize, f = get_image(*args)
                # Increment for send
                logical_clock[0] += 1
                print(f"Server {port}: Sending image locally at clock {logical_clock[0]}")
                # Send clock, size, file
                conn.sendall(struct.pack("Q", logical_clock[0]))
                conn.sendall(struct.pack("Q", filesize))
                conn.sendfile(f)
                f.close()
            elif func_name == "get_image_size":
                filesize = get_image_size(*args)
                # Increment for send
                logical_clock[0] += 1
                print(f"Server {port}: Sending size locally at clock {logical_clock[0]}")
                # Send clock, size
                conn.sendall(struct.pack("Q", logical_clock[0]))
                conn.sendall(struct.pack("Q", filesize))
            else:
                logical_clock[0] += 1  # Increment for error send
                error_msg = json.dumps({"error": f"Function {func_name} not found."}).encode()
                conn.sendall(struct.pack("Q", logical_clock[0]))
                conn.sendall(struct.pack("Q", len(error_msg)))
                conn.sendall(error_msg)

    except Exception as e:
        logical_clock[0] += 1  # Increment for error send
        error_msg = json.dumps({"error": str(e)}).encode()
        conn.sendall(struct.pack("Q", logical_clock[0]))
        conn.sendall(struct.pack("Q", len(error_msg)))
        conn.sendall(error_msg)

def handle_client(conn: socket.socket, no_of_threads: int, port: int, peer_host: str, peer_port: int, logical_clock: list):
    with conn:
        while True:
            try:
                # Read 8-byte length prefix
                size_data = recv_exact(conn, 8)
                (size,) = struct.unpack("Q", size_data)
                request = recv_exact(conn, size).decode()

                print(f"Server {port}: Received raw request: {request}")
                data = json.loads(request)
                received_clock = data["clock"]
                # Update clock on receive
                logical_clock[0] = max(logical_clock[0], received_clock) + 1
                print(f"Server {port}: Received request with client clock {received_clock}, updated to {logical_clock[0]}")

                handle_request(conn, request, port, peer_host, peer_port, logical_clock)
            except ConnectionError:
                print(f"Server {port}: Client {no_of_threads} disconnected")
                break

def main():
    if len(sys.argv) != 3:
        print("Usage: python server.py <port> <peer_port>")
        sys.exit(1)

    host = "127.0.0.1"
    port = int(sys.argv[1])
    peer_host = "127.0.0.1"
    peer_port = int(sys.argv[2])
    logical_clock = [0]  # Mutable list to share across threads (simple demo, not thread-safe)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"Server listening on {host}:{port}, peer at {peer_port}...")
        no_of_threads = 0

        # Create a thread pool with a maximum of 10 workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                conn, _ = s.accept()
                no_of_threads += 1
                print(f"Server {port}: Thread {no_of_threads} spawned for client {no_of_threads}")
                # Submit the client handling to the thread pool
                executor.submit(handle_client, conn, no_of_threads, port, peer_host, peer_port, logical_clock)

if __name__ == "__main__":
    main()
