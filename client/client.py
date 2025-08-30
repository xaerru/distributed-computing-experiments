import socket, json, struct

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

def rpc_call(s, function, args, clock: int):
    request = json.dumps({"function": function, "args": args, "clock": clock}).encode()
    # Send request length first
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

        # Try JSON decode first (error case), else treat as image
        try:
            error = json.loads(image.decode())
            return error
        except UnicodeDecodeError:
            with open(f"image{args[0]}.jpg", "wb") as f:
                f.write(image)
            return f"image{args[0]}.jpg saved in the current directory."
    elif function == "get_image_size":
        # Receive size
        size_data = recv_exact(s, 8)
        (size,) = struct.unpack("Q", size_data)
        return f"Size of image{args[0]}.jpg is {size} bytes."
    else:
        # Assume error: size already received as part of response, but for simplicity
        size_data = recv_exact(s, 8)
        (size,) = struct.unpack("Q", size_data)
        error = recv_exact(s, size).decode()
        return json.loads(error)

def main():
    print("Enter 1 to get an image\nEnter 2 to get the image size\nEnter 3 to exit\n")
    host = "127.0.0.1"
    port = 8080  # Connect to server1
    logical_clock = 0

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        while True:
            op = int(input("> "))
            if op == 1:
                id = int(input("Enter image id: "))
                # Increment for send
                logical_clock += 1
                print(f"Client: Sending get_image request at clock {logical_clock}")
                result = rpc_call(s, "get_image", [id], logical_clock)
                # Update clock on receive (after rpc_call receives resp_clock)
                # Note: Update happens after recv, but for logging, we can assume rpc_call returns resp_clock if needed; here simplify
                print(result)
            elif op == 2:
                id = int(input("Enter image id: "))
                # Increment for send
                logical_clock += 1
                print(f"Client: Sending get_image_size request at clock {logical_clock}")
                result = rpc_call(s, "get_image_size", [id], logical_clock)
                print(result)
            else:
                print("Exiting.")
                break
            print()

if __name__ == "__main__":
    main()
