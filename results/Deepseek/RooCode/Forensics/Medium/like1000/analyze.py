#!/usr/bin/env python3
from PIL import Image
import sys

def analyze_image(path):
    img = Image.open(path)
    print(f"Image size: {img.size}")
    print(f"Mode: {img.mode}")
    
    # Check if there's any unusual color distribution
    # Get pixel data
    pixels = img.load()
    width, height = img.size
    
    # Check first few pixels
    print("First 10 pixel values (RGB):")
    for y in range(min(10, height)):
        for x in range(min(10, width)):
            print(f"  ({x},{y}): {pixels[x, y]}")
    
    # Look for ASCII values in LSB
    print("\nChecking LSB of red channel for ASCII...")
    ascii_chars = []
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            lsb = r & 1
            ascii_chars.append(chr(lsb + 48))  # just for demo
            if len(ascii_chars) > 100:
                break
        if len(ascii_chars) > 100:
            break
    # Not useful
    
    # Try to extract hidden data via LSB
    print("\nAttempting LSB extraction (first 100 bytes):")
    data = []
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            data.append(r & 1)
            data.append(g & 1)
            data.append(b & 1)
            if len(data) >= 800:
                break
        if len(data) >= 800:
            break
    
    # Convert bits to bytes
    bytes_list = []
    for i in range(0, len(data) - 7, 8):
        byte = 0
        for j in range(8):
            byte |= data[i + j] << j
        bytes_list.append(byte)
    
    # Try to interpret as ASCII
    text = ''.join(chr(b) for b in bytes_list if 32 <= b < 127)
    print(f"Extracted ASCII (first 200 chars): {text[:200]}")
    
    # Check for PNG chunks after IDAT
    with open(path, 'rb') as f:
        content = f.read()
        # Search for flag pattern
        import re
        flag_pattern = re.compile(b'picoCTF\{.*?\}')
        matches = flag_pattern.findall(content)
        if matches:
            print(f"Found flag in raw bytes: {matches}")
        else:
            print("No flag pattern in raw bytes")
        
        # Search for any text
        text_sections = re.findall(b'[A-Za-z0-9_\-]{10,}', content)
        if text_sections:
            print("Possible text sections (first 5):")
            for ts in text_sections[:5]:
                print(f"  {ts}")

if __name__ == "__main__":
    analyze_image("extracted/flag.png")