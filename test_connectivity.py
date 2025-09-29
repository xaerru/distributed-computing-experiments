#!/usr/bin/env python3
import socket
import json
import struct

def test_edge_server(host, port, image_id):
    try:
        print(f"Testing {host}:{port} with image {image_id}")
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(10)
            s.connect((host, port))
            
            # Create request
            request = json.dumps({
                "function": "get_image_size", 
                "args": [image_id], 
                "clock": 1
            }).encode()
            
            # Send request
            s.sendall(struct.pack("Q", len(request)))
            s.sendall(request)
            
            # Read response
            resp_clock_data = s.recv(8)
            if len(resp_clock_data) != 8:
                print(f"  Failed: Expected 8 bytes for clock, got {len(resp_clock_data)}")
                return False
                
            (resp_clock,) = struct.unpack("Q", resp_clock_data)
            print(f"  Response clock: {resp_clock}")
            
            # Read size
            size_data = s.recv(8)
            if len(size_data) != 8:
                print(f"  Failed: Expected 8 bytes for size, got {len(size_data)}")
                return False
                
            (size,) = struct.unpack("Q", size_data)
            print(f"  Image size: {size} bytes")
            
            if size > 0:
                print(f"  SUCCESS: Edge server {host}:{port} responded correctly!")
                return True
            else:
                print(f"  WARNING: Size is 0, might indicate an error")
                return False
                
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

if __name__ == "__main__":
    # Test all edge servers
    edge_servers = [
        ("localhost", 8001),
        ("localhost", 8002), 
        ("localhost", 8003)
    ]
    
    image_id = 5  # Use image5.jpg which exists
    
    print("Testing edge servers...")
    print("=" * 50)
    
    for host, port in edge_servers:
        test_edge_server(host, port, image_id)
        print()
    
    print("Testing canonical server directly...")
    test_edge_server("localhost", 9000, image_id)