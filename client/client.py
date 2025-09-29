import socket, json, struct

EDGE_BASE_PORT = 8001
NUM_EDGES = 5
HOST = '127.0.0.1'

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

def rpc_call(s: socket.socket, function: str, args: list, clock: int):
    """
    Send framed RPC to an already-connected socket `s` and return the response.
    The framing matches your project's format:
      - Request: 8-byte length (unsigned long long) + JSON bytes
      - Response: 8-byte clock (unsigned long long) + function-specific payload
    """
    request = json.dumps({"function": function, "args": args, "clock": clock}).encode()
    # Send request length first
    s.sendall(struct.pack("Q", len(request)))
    s.sendall(request)

    # Read response clock
    resp_clock_data = recv_exact(s, 8)
    (resp_clock,) = struct.unpack("Q", resp_clock_data)

    if function == "get_image":
        # Next 8-byte size then image bytes (or JSON error)
        size_data = recv_exact(s, 8)
        (size,) = struct.unpack("Q", size_data)
        image = recv_exact(s, size)
        # Try to interpret as an error JSON; if not, write to file
        try:
            err = json.loads(image.decode())
            return resp_clock, err
        except Exception:
            return resp_clock, image
    elif function == "get_image_size":
        size_data = recv_exact(s, 8)
        (size,) = struct.unpack("Q", size_data)
        return resp_clock, {"size": size}
    else:
        # Generic: read a following 8-byte length and payload
        size_data = recv_exact(s, 8)
        (size,) = struct.unpack("Q", size_data)
        payload = recv_exact(s, size).decode() if size > 0 else ""
        try:
            return resp_clock, json.loads(payload)
        except Exception:
            return resp_clock, payload

def pick_edge_for_image(img_id:int):
    idx = img_id % NUM_EDGES
    port = EDGE_BASE_PORT + idx
    return HOST, port

def main():
    logical_clock = 0
    print("Client (LB) ready. This client forwards requests to edge chosen by image_id % 5 (ports 8001..8005).")
    while True:
        print("Choose: 1) get_image  2) get_image_size  3) exit")
        try:
            op = int(input("> ").strip())
        except Exception:
            print("Invalid input, try again.")
            continue

        if op == 3:
            print("Exiting.")
            break

        try:
            img_id = int(input("Enter image id: ").strip())
        except Exception:
            print("Invalid image id.")
            continue

        host, port = pick_edge_for_image(img_id)

        # Open connection to selected edge and perform RPC
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
                if op == 1:
                    logical_clock += 1
                    print(f"Client: Sending get_image request at clock {logical_clock}")
                    resp_clock, resp = rpc_call(s, "get_image", [img_id], logical_clock)
                    # If resp is dict => error, else bytes => image
                    if isinstance(resp, dict) and resp.get("error"):
                        print("Error from edge:", resp)
                    else:
                        # Save image to file with same naming as original client
                        fname = f"downloaded_image_{img_id}.jpg"
                        with open(fname, "wb") as f:
                            f.write(resp)
                        print(f"Saved {fname} (from edge {port})")
                elif op == 2:
                    logical_clock += 1
                    print(f"Client: Sending get_image_size request at clock {logical_clock}")
                    resp_clock, resp = rpc_call(s, "get_image_size", [img_id], logical_clock)
                    if isinstance(resp, dict) and resp.get("size") is not None:
                        print(f"Size: {resp['size']} bytes (from edge {port})")
                    else:
                        print("Error from edge:", resp)
                else:
                    print("Unknown operation.")
        except Exception as e:
            print(f"Client: error contacting edge {port} -> {e}")

        print()

if __name__ == "__main__":
    main()
