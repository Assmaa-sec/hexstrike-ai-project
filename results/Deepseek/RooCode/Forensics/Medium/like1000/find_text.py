#!/usr/bin/env python3
import zlib
import struct

def get_pixel_data(path):
    with open(path, 'rb') as f:
        f.read(8)
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
        decompressed = zlib.decompress(idat_data)
        return decompressed

data = get_pixel_data('extracted/flag.png')
width = 1642
height = 1095
# Each pixel is RGB, no filter
print(f"Total bytes: {len(data)}")
# Convert to list of pixels
pixels = []
for y in range(height):
    row = []
    for x in range(width):
        idx = (y * width + x) * 3
        r = data[idx]
        g = data[idx + 1]
        b = data[idx + 2]
        row.append((r, g, b))
    pixels.append(row)

# Find rows with non-white pixels
dark_rows = []
for y, row in enumerate(pixels):
    dark_count = sum(1 for r, g, b in row if r < 250 or g < 250 or b < 250)
    if dark_count > 0:
        dark_rows.append(y)
        if len(dark_rows) > 10:
            break

print(f"Rows with dark pixels (first 10): {dark_rows[:10]}")

# Let's examine a specific row (e.g., row 177 from earlier)
y = 177
row = pixels[y]
print(f"\nRow {y} first 50 pixels (RGB):")
for x in range(50):
    print(f"{row[x]}", end=' ')
print()

# Convert to ASCII art by threshold
threshold = 200
ascii_row = ''
for x in range(min(200, width)):
    r, g, b = row[x]
    if r < threshold or g < threshold or b < threshold:
        ascii_row += '#'
    else:
        ascii_row += ' '
print(f"\nASCII representation (threshold {threshold}):")
print(ascii_row)

# Look for patterns across rows
print("\nScanning for text patterns...")
text_rows = []
for y in range(height):
    row = pixels[y]
    dark = any(r < 200 or g < 200 or b < 200 for r, g, b in row)
    if dark:
        text_rows.append(y)
        if len(text_rows) > 30:
            break

print(f"First {len(text_rows)} rows with dark pixels: {text_rows}")

# Print a slice of the image as ASCII
print("\nASCII art of region (rows 170-190, cols 650-750):")
for y in range(170, 190):
    line = ''
    for x in range(650, 750):
        r, g, b = pixels[y][x - 650]
        if r < 200 or g < 200 or b < 200:
            line += '#'
        else:
            line += ' '
    print(f"{y:3d}: {line}")