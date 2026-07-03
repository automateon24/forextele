import os

path = r"C:\cursor\options\niftyopt\SETUP_ALL_SCHEDULES.bat"
with open(path, "rb") as f:
    raw = f.read()

print(f"File size: {len(raw)} bytes")
has_cr = b'\r' in raw
has_lf = b'\n' in raw
print(f"Has CR: {has_cr}")
print(f"Has LF: {has_lf}")

# Let's fix line endings to CRLF
normalized = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n').replace(b'\n', b'\r\n')

with open(path, "wb") as f:
    f.write(normalized)
print("Line endings normalized to CRLF!")
