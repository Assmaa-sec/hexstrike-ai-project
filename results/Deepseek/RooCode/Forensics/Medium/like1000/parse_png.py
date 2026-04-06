#!/usr/bin/env python3
import struct
import sys

def parse_png(path):
    with open(path, 'rb') as f:
        # PNG signature
        signature = f.read(8)
        print(f"Signature: {signature.hex()}")
        
        while True:
            chunk = f.read(8)
            if not chunk or len(chunk) < 8:
                break
            length = struct.unpack('>I', chunk[:4])[0]
            chunk_type = chunk[4:].decode('ascii')
            print(f"Chunk: {chunk_type} length {length}")
            
            data = f.read(length)
            crc = f.read(4)
            
            if chunk_type in ['tEXt', 'zTXt', 'iTXt']:
                print(f"  Text chunk data: {data[:100]}")
                try:
                    if chunk_type == 'tEXt':
                        # null-separated keyword and text
                        parts = data.split(b'\x00', 1)
                        if len(parts) == 2:
                            keyword, text = parts
                            print(f"    Keyword: {keyword.decode()}")
                            print(f"    Text: {text.decode()}")
                except:
                    pass
            elif chunk_type == 'IDAT':
                # skip
                pass
            elif chunk_type == 'IEND':
                break

if __name__ == "__main__":
    parse_png("extracted/flag.png")