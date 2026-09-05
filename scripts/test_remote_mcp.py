import requests
import json
import sseclient
import threading
import time

BASE_URL = "http://localhost:8000"

def listen_sse(url, results):
    response = requests.get(url, stream=True)
    client = sseclient.SSEClient(response)
    for event in client.events():
        if event.event == "endpoint":
            results['endpoint'] = event.data
        else:
            results['messages'].append(json.loads(event.data))
        if len(results['messages']) >= 2:
            break

def test_remote():
    results = {'endpoint': None, 'messages': []}
    
    thread = threading.Thread(target=listen_sse, args=(f"{BASE_URL}/sse", results))
    thread.start()
    
    timeout = 5
    start = time.time()
    while not results['endpoint'] and time.time() - start < timeout:
        time.sleep(0.1)
    
    if not results['endpoint']:
        print("Error: No endpoint recibido dentro del tiempo de espera.")
        return

    endpoint = results['endpoint']
    print(f"Conectado al endpoint: {endpoint}")
    
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }
    resp = requests.post(f"{BASE_URL}{endpoint}", json=init_msg)
    print(f"Initialize sent. Status: {resp.status_code}")
    
    tool_msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "consultar_directorio",
            "arguments": {"query": "Ana"}
        }
    }
    resp = requests.post(f"{BASE_URL}{endpoint}", json=tool_msg)
    print(f"Llamada a tool enviada. Status: {resp.status_code}")
    
    thread.join(timeout=5)
    
    print("\nMensajes recibidos via SSE:")
    for msg in results['messages']:
        print(json.dumps(msg, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_remote()
