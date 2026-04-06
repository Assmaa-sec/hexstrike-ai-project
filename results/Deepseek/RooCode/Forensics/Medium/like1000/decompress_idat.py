#!/usr/bin/env python3
import zlib
import struct
import re

def extract_idat(path):
    with open(path, 'rb') as f:
        f.read(8)  # signature
        idat_data = b''
        while True:
            chunk = f.read(8)
            if not chunk:
                break
            length = struct.unpack('>I', chunk[:4])[0]
            chunk_type = chunk[4:].decode('ascii')
            data = f.read(length)
            crc = f.read(4)
            if chunk_type == 'IDAT':
                idat_data += data
            elif chunk_type == 'IEND':
                break
        return idat_data

idat = extract_idat('extracted/flag.png')
print(f"IDAT compressed size: {len(idat)}")
# Decompress
try:
    decompressed = zlib.decompress(idat)
    print(f"Decompressed size: {len(decompressed)}")
    # Search for flag pattern
    flag_pattern = re.compile(b'picoCTF\{[^}]+\}')
    matches = flag_pattern.findall(decompressed)
    if matches:
        print("Found flag in decompressed data:")
        for m in matches:
            print(m.decode())
    else:
        # Search for any ASCII text
        ascii_text = re.findall(b'[A-Za-z0-9_\-]{10,}', decompressed)
        if ascii_text:
            print("Possible text strings (first 10):")
            for t in ascii_text[:10]:
                print(f"  {t}")
        else:
            print("No flag pattern found in decompressed data.")
except Exception as e:
    print(f"Decompression error: {e}")