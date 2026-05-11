#!/usr/bin/env python3
"""
Test script for API key settings endpoints
"""

import requests
import json

BASE_URL = "http://localhost:8000"

print("=" * 60)
print("Testing API Key Settings Endpoints")
print("=" * 60)

# Step 1: Register a test user
print("\n1. Registering test user...")
register_response = requests.post(
    f"{BASE_URL}/api/auth/register",
    json={"email": "apikey-test@example.com", "name": "API Key Tester"}
)
print(f"Status: {register_response.status_code}")
register_data = register_response.json()
jwt_token = register_data.get("access_token")
print(f"JWT Token: {jwt_token[:50]}...")

# Step 2: Save OpenAI API key
print("\n2. Saving OpenAI API key...")
openai_response = requests.post(
    f"{BASE_URL}/api/settings/api-keys",
    headers={"Authorization": f"Bearer {jwt_token}"},
    json={
        "service": "openai",
        "api_key": "sk-proj-test123456789"
    }
)
print(f"Status: {openai_response.status_code}")
print(f"Response: {json.dumps(openai_response.json(), indent=2)}")

# Step 3: Save Ollama API key with model
print("\n3. Saving Ollama API key with model...")
ollama_response = requests.post(
    f"{BASE_URL}/api/settings/api-keys",
    headers={"Authorization": f"Bearer {jwt_token}"},
    json={
        "service": "ollama",
        "api_key": "ollama",
        "model": "llama2"
    }
)
print(f"Status: {ollama_response.status_code}")
print(f"Response: {json.dumps(ollama_response.json(), indent=2)}")

# Step 4: List all API keys
print("\n4. Listing all configured API keys...")
list_response = requests.get(
    f"{BASE_URL}/api/settings/api-keys",
    headers={"Authorization": f"Bearer {jwt_token}"}
)
print(f"Status: {list_response.status_code}")
print(f"Response: {json.dumps(list_response.json(), indent=2)}")

# Step 5: Get specific API key setting
print("\n5. Getting specific API key setting (OpenAI)...")
get_response = requests.get(
    f"{BASE_URL}/api/settings/api-keys/openai",
    headers={"Authorization": f"Bearer {jwt_token}"}
)
print(f"Status: {get_response.status_code}")
print(f"Response: {json.dumps(get_response.json(), indent=2)}")

# Step 6: Update API key
print("\n6. Updating OpenAI API key...")
update_response = requests.put(
    f"{BASE_URL}/api/settings/api-keys/openai",
    headers={"Authorization": f"Bearer {jwt_token}"},
    json={
        "service": "openai",
        "api_key": "sk-proj-updated123456789"
    }
)
print(f"Status: {update_response.status_code}")
print(f"Response: {json.dumps(update_response.json(), indent=2)}")

# Step 7: Delete API key
print("\n7. Deleting Ollama API key...")
delete_response = requests.delete(
    f"{BASE_URL}/api/settings/api-keys/ollama",
    headers={"Authorization": f"Bearer {jwt_token}"}
)
print(f"Status: {delete_response.status_code}")

# Step 8: Verify deletion
print("\n8. Listing API keys after deletion...")
final_list = requests.get(
    f"{BASE_URL}/api/settings/api-keys",
    headers={"Authorization": f"Bearer {jwt_token}"}
)
print(f"Status: {final_list.status_code}")
print(f"Response: {json.dumps(final_list.json(), indent=2)}")

print("\n" + "=" * 60)
print("API Key Settings Testing Complete!")
print("=" * 60)
