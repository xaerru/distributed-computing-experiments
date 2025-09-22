#!/usr/bin/env python3
import socket
import json
import struct

def recv_exact(sock, n: int) -> bytes:
    data = b""
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            raise ConnectionError("Connection closed")
        data += packet
    return data

def test_get_image(host, port, image_id):
    try:
        print(f"Testing get_image on {host}:{port} with image {image_id}")
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((host, port))
            
            # Create request
            request = json.dumps({
                "function": "get_image", 
                "args": [image_id], 
                "clock": 1
            }).encode()
            
            # Send request
            s.sendall(struct.pack("Q", len(request)))
            s.sendall(request)
            
            # Read response clock
            resp_clock_data = recv_exact(s, 8)
            (resp_clock,) = struct.unpack("Q", resp_clock_data)
            print(f"  Response clock: {resp_clock}")
            
            # Read size
            size_data = recv_exact(s, 8)
            (size,) = struct.unpack("Q", size_data)
            print(f"  Image size: {size} bytes")
            
            if size > 0:
                # Read image data
                image_data = recv_exact(s, size)
                print(f"  Received {len(image_data)} bytes of image data")
                
                # Save image
                filename = f"test_image_{image_id}_{host.replace('.', '_')}_{port}.jpg"
                with open(filename, "wb") as f:
                    f.write(image_data)
                print(f"  Saved image as: {filename}")
                print(f"  SUCCESS!")
                return True
            else:
                print(f"  WARNING: Size is 0")
                return False
                
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Test downloading an image from an edge server
    print("Testing image download...")
    print("=" * 50)
    
    # Test edge server 0 (localhost:8001)
    success = test_get_image("localhost", 8001, 5)
    
    if success:
        print("\nImage download test PASSED!")
    else:
        print("\nImage download test FAILED!")