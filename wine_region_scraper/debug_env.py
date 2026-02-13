import os
from dotenv import load_dotenv

# Check raw file
with open('.env', 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'PINECONE_API_KEY' in line:
            print(f"Line {i}: {repr(line)}")
            key_value = line.split('=', 1)[1].strip()
            print(f"Key value length: {len(key_value)}")
            print(f"Key value: {key_value}")

print("\n--- After load_dotenv() ---")
load_dotenv()
key = os.getenv('PINECONE_API_KEY')
print(f"Loaded key length: {len(key) if key else 0}")
print(f"Loaded key: {key}")
