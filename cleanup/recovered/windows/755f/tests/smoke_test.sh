#!/usr/bin/env bash
set -e

# Run each compiled binary with a short timeout
for prog in BCHvsHamming Hamming32bit1Gb Hamming64bit128Gb SATDemo; do
    echo "Testing $prog"
    # Allow a bit more breathing room on slower environments so the
    # smoke tests don't spuriously fail with timeout code 124.
    timeout 15s ./"$prog" --smoke >/dev/null
done

# Basic check of the ECC selector
echo "Testing ecc_selector.py"
python ecc_selector.py 1e-6 2 0.6 1e-15 1 --sustainability >/dev/null

echo "All smoke tests passed."
