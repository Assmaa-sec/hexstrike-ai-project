#!/usr/bin/env python3
import tarfile
import os
import sys

def extract_nested_tar(start_tar, output_dir):
    current_tar = start_tar
    count = 0
    max_iterations = 2000  # safety limit
    
    while True:
        count += 1
        print(f"Iteration {count}: extracting {current_tar}")
        
        # Extract the tar
        with tarfile.open(current_tar, 'r') as tf:
            members = tf.getmembers()
            # List members
            for member in members:
                print(f"  - {member.name}")
            
            # Extract all members
            tf.extractall(path=output_dir)
        
        # Check what was extracted
        extracted_files = os.listdir(output_dir)
        print(f"  Extracted files: {extracted_files}")
        
        # Look for the next tar file
        next_tar = None
        for f in extracted_files:
            if f.endswith('.tar'):
                next_tar = os.path.join(output_dir, f)
                break
        
        # Remove filler.txt if present
        for f in extracted_files:
            if f == 'filler.txt':
                os.remove(os.path.join(output_dir, f))
        
        # If no more tar files, we're done
        if next_tar is None:
            print("No more tar files found. Extraction complete.")
            break
        
        # Remove the current tar file (optional)
        if current_tar != start_tar:
            os.remove(current_tar)
        
        # Set next iteration
        current_tar = next_tar
        
        if count >= max_iterations:
            print("Reached max iterations, stopping.")
            break
    
    print(f"Total iterations: {count}")
    return count

if __name__ == "__main__":
    start_tar = "1000.tar"
    output_dir = "extracted"
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    extract_nested_tar(start_tar, output_dir)
    
    # List final contents
    print("\nFinal contents of extracted directory:")
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            path = os.path.join(root, f)
            print(f"  {path}")
            # If it's a text file, maybe read it
            if f.endswith('.txt') or 'flag' in f.lower():
                try:
                    with open(path, 'r') as fp:
                        content = fp.read(200)
                        print(f"    Content preview: {content}")
                except:
                    pass