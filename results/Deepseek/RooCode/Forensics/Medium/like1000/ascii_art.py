#!/usr/bin/env python3
from PIL import Image
import sys

def image_to_ascii(path, width=100):
    img = Image.open(path)
    # Convert to grayscale
    img = img.convert('L')
    # Resize
    aspect = img.height / img.width
    height = int(width * aspect * 0.5)  # adjust for character aspect
    img = img.resize((width, height))
    
    pixels = img.getdata()
    ascii_chars = '@%#*+=-:. '
    
    output = ''
    for i, pixel in enumerate(pixels):
        if i % width == 0 and i != 0:
            output += '\n'
        # Map pixel value (0-255) to ascii index
        index = pixel * (len(ascii_chars) - 1) // 255
        output += ascii_chars[index]
    return output

if __name__ == "__main__":
    ascii_art = image_to_ascii('extracted/flag.png', width=120)
    print(ascii_art)
    # Also look for any text patterns
    lines = ascii_art.split('\n')
    for i, line in enumerate(lines):
        if 'pico' in line.lower() or 'flag' in line.lower() or 'ctf' in line.lower():
            print(f"Potential flag line {i}: {line}")