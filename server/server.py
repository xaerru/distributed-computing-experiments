import socket, json, os, struct, concurrent.futures

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

def handle_request(conn: socket.socket, request: str):
    try:
        data = json.loads(request)
        func_name = data["function"]
        args = data["args"]

        if func_name == "get_image":
            filesize, f = get_image(*args)
            # send 8-byte size
            conn.sendall(struct.pack("Q", filesize))

            # send file
            conn.sendfile(f)

            f.close()
        elif func_name == "get_image_size":
            filesize = get_image_size(*args)

            # send 8-byte size
            conn.sendall(struct.pack("Q", filesize))
        else:
            error_msg = json.dumps({"error": f"Function {func_name} not found."}).encode()
            conn.sendall(struct.pack("Q", len(error_msg)))
            conn.sendall(error_msg)

    except Exception as e:
        error_msg = json.dumps({"error": str(e)}).encode()
        conn.sendall(struct.pack("Q", len(error_msg)))
        conn.sendall(error_msg)

def handle_client(conn: socket.socket, no_of_threads: int):
    with conn:
        while True:
            try:
                # read 8-byte length prefix
                size_data = recv_exact(conn, 8)
                (size,) = struct.unpack("Q", size_data)
                request = recv_exact(conn, size).decode()

                print(f"Received: {request}")
                handle_request(conn, request)
            except ConnectionError:
                print(f"Client {no_of_threads} disconnected")
                break

def main():
    host = "127.0.0.1"
    port = 8080
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, port))
        s.listen()
        print(f"Server listening on {host}:{port}...")
        global no_of_threads
        no_of_threads = 0

        # Create a thread pool with a maximum of 10 workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            while True:
                conn, _ = s.accept()
                no_of_threads += 1
                print(f"Thread {no_of_threads} spawned for client {no_of_threads}")
                # Submit the client handling to the thread pool
                executor.submit(handle_client, conn, no_of_threads)

if __name__ == "__main__":
    main()
