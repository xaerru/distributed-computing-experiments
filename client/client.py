import socket, json, struct

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

def rpc_call(s, function, args):
    request = json.dumps({"function": function, "args": args}).encode()
    # send request length first
    s.sendall(struct.pack("Q", len(request)))
    s.sendall(request)

    if function == "get_image":
        # first 8 bytes = size of image
        size_data = recv_exact(s, 8)
        (size,) = struct.unpack("Q", size_data)
        # receive image
        image = recv_exact(s, size)

        # try JSON decode first (error case), else treat as image
        try:
            return json.loads(image.decode())
        except UnicodeDecodeError:
            with open(f"image{args[0]}.jpg", "wb") as f:
                f.write(image)
            return f"image{args[0]}.jpg saved in the current directory."
    elif function == "get_image_size":
        # first 8 bytes = size of image
        size_data = recv_exact(s, 8)
        (size,) = struct.unpack("Q", size_data)
        return f"Size of image{args[0]}.jpg is {size} bytes."

def main():
    print("Enter 1 to get an image\nEnter 2 to get the image size\nEnter 3 to exit\n")
    host = "127.0.0.1"
    port = 8080
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        while True:
            op = int(input("> "))
            if op == 1:
                id = int(input("Enter image id: "))

                result = rpc_call(s, "get_image", [id])
                print(result)
            elif op == 2:
                id = int(input("Enter image id: "))

                result = rpc_call(s, "get_image_size", [id])
                print(result)
            else:
                print("Exiting.")
                break
            print()

if __name__ == "__main__":
    main()
