import socket, json, struct, os, threading

HOST = "0.0.0.0"  # Listen on all interfaces for Docker
PORT = 9000  # canonical server port (hardcoded)

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

def get_image_path(id: int):
    return os.path.join(os.path.dirname(__file__), "images", f"image{id}.jpg")

def handle_request(conn: socket.socket):
    with conn:
        try:
            size_data = recv_exact(conn, 8)
            (size,) = struct.unpack("Q", size_data)
            request = recv_exact(conn, size).decode()
            data = json.loads(request)
            func = data.get("function")
            args = data.get("args", [])
            # Incremental logical clock is not used here; echo back a dummy clock 0
            # Always respond with clock 0
            conn.sendall(struct.pack("Q", 0))
            if func == "get_image":
                conn.getsockname()[1]
                img_id = args[0]
                path = get_image_path(img_id)
                if not os.path.exists(path):
                    err = json.dumps({"error": f"image{img_id}.jpg not found on canonical server"}).encode()
                    conn.sendall(struct.pack("Q", len(err)))
                    conn.sendall(err)
                else:
                    print(f"Received get_image from port {conn.getsockname()[1]} for image{img_id}.jpg")
                    filesize = os.path.getsize(path)
                    conn.sendall(struct.pack("Q", filesize))
                    # send file bytes
                    with open(path, "rb") as f:
                        conn.sendfile(f)
                    print(f"Sent image{img_id}.jpg to port {conn.getsockname()[1]}")
            elif func == "get_image_size":
                img_id = args[0]
                path = get_image_path(img_id)
                print(f"Received get_image_size from port {conn.getsockname()[1]} for image{img_id}.jpg")
                if not os.path.exists(path):
                    err = json.dumps({"error": f"image{img_id}.jpg not found on canonical server"}).encode()
                    conn.sendall(struct.pack("Q", len(err)))
                    conn.sendall(err)
                else:
                    filesize = os.path.getsize(path)
                    conn.sendall(struct.pack("Q", filesize))
                    print(f"Sent image{img_id}.jpg's size to port {conn.getsockname()[1]}")
            else:
                err = json.dumps({"error": f"Unknown function {func}"}).encode()
                conn.sendall(struct.pack("Q", len(err)))
                conn.sendall(err)
        except Exception as e:
            try:
                err = json.dumps({"error": str(e)}).encode()
                conn.sendall(struct.pack("Q", 0))
                conn.sendall(struct.pack("Q", len(err)))
                conn.sendall(err)
            except Exception:
                pass

def main():
    print(f"Canonical server starting on {HOST}:{PORT}") 
    os.chdir(os.path.dirname(__file__))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        while True:
            conn , _ = s.accept()
            threading.Thread(target=handle_request, args=(conn,), daemon=True).start()

if __name__ == '__main__':
    main()
