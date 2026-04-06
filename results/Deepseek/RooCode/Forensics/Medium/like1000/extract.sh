#!/bin/bash
set -e

cd "$(dirname "$0")"
mkdir -p extracted
cp 1000.tar extracted/
cd extracted

counter=1000
while [ $counter -gt 0 ]; do
    if [ ! -f "${counter}.tar" ]; then
        echo "File ${counter}.tar not found, breaking."
        break
    fi
    echo "Extracting ${counter}.tar"
    tar -xf "${counter}.tar"
    rm -f filler.txt
    # Remove the tar we just extracted
    rm "${counter}.tar"
    ((counter--))
done

echo "Extraction complete. Remaining files:"
ls -la