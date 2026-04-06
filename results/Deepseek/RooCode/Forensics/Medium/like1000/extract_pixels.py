#!/usr/bin/env python3
from PIL import Image
import sys

img = Image.open('extracted/flag.png')
pixels = img.load()
width, height = img.size

non_white = []
for y in range(height):
    for x in range(width):
        r, g, b = pixels[x, y]
        if r != 255 or g != 255 or b != 255:
            non_white.append((x, y, r, g, b))

print(f"Total non-white pixels: {len(non_white)}")
if non_white:
    # Sort by y then x
    non_white.sort(key=lambda p: (p[1], p[0]))
    print("First 50 non-white pixels (x, y, r, g, b):")
    for p in non_white[:50]:
        print(f"  {p}")
    
    # Try to interpret RGB values as ASCII
    print("\nAttempting to interpret RGB as ASCII (assuming each pixel is a character):")
    chars = []
    for x, y, r, g, b in non_white:
        # Maybe the flag is encoded in one channel
        if 32 <= r < 127:
            chars.append(chr(r))
        if 32 <= g < 127:
            chars.append(chr(g))
        if 32 <= b < 127:
            chars.append(chr(b))
    print(''.join(chars))
    
    # Try to interpret as hex
    print("\nRGB values as hex:")
    for x, y, r, g, b in non_white[:20]:
        print(f"  #{r:02x}{g:02x}{b:02x}", end=' ')
    print()
    
    # Check if they form a pattern (maybe flag is spelled)
    # Let's see if the coordinates are sequential
    print("\nCoordinate pattern:")
    prev_x = non_white[0][0]
    prev_y = non_white[0][1]
    for i, (x, y, r, g, b) in enumerate(non_white[1:]):
        dx = x - prev_x
        dy = y - prev_y
        print(f"  {i}: delta ({dx}, {dy})")
        prev_x, prev_y = x, y