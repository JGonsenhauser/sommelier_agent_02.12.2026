#!/usr/bin/env python3
"""Test XAI embedding access directly."""
from dotenv import load_dotenv
load_dotenv()

import os
from openai import OpenAI
from config import settings

print("\n" + "="*60)
print("Testing XAI Embedding Access")
print("="*60)

# Step 1: Get the decrypted key
print("\n[1] Decrypting XAI API key...")
try:
    decrypted_key = settings.get_decrypted_xai_key()
    print(f"[OK] Decrypted key: {decrypted_key[:10]}...{decrypted_key[-5:]}")
    print(f"     Key length: {len(decrypted_key)}")
except Exception as e:
    print(f"[ERROR] Decryption failed: {e}")
    exit(1)

# Step 2: Test connection
print("\n[2] Testing XAI API connection...")
client = OpenAI(
    api_key=decrypted_key,
    base_url="https://api.x.ai/v1"
)

# Step 3: List available models
print("\n[3] Listing available XAI models...")
try:
    models = client.models.list()
    print(f"[OK] Found {len(models.data)} models:")
    for model in sorted(models.data, key=lambda m: m.id):
        print(f"   - {model.id}")
except Exception as e:
    print(f"[ERROR] Could not list models: {e}")

# Step 4: Try grok-embedding
print("\n[4] Testing 'grok-embedding' model...")
try:
    response = client.embeddings.create(
        model="grok-embedding",
        input="pinot noir"
    )
    print(f"[OK] grok-embedding works!")
    print(f"     Dimension: {len(response.data[0].embedding)}")
except Exception as e:
    print(f"[ERROR] grok-embedding failed: {e}")

# Step 5: Try alternative XAI embedding model names
alternatives = [
    "grok-2-embedding",
    "grok-3-embedding",
    "grok-embedding-beta",
    "embedding-grok",
    "v1-embedding",
]
print(f"\n[5] Trying alternative embedding model names...")
for model_name in alternatives:
    try:
        response = client.embeddings.create(
            model=model_name,
            input="test"
        )
        print(f"[OK] '{model_name}' WORKS! Dimension: {len(response.data[0].embedding)}")
    except Exception as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "not found" in error_msg.lower():
            print(f"   [--] '{model_name}' - not found")
        else:
            print(f"   [??] '{model_name}' - {error_msg[:80]}")

# Step 6: Test chat model works
print(f"\n[6] Testing chat model '{settings.xai_chat_model}'...")
try:
    response = client.chat.completions.create(
        model=settings.xai_chat_model,
        messages=[{"role": "user", "content": "Say hello in one word"}],
        max_tokens=10
    )
    print(f"[OK] Chat model works: {response.choices[0].message.content}")
except Exception as e:
    print(f"[ERROR] Chat model failed: {e}")
