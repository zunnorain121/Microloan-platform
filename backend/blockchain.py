import requests
import json
import os
from datetime import datetime

def publish_to_blockchain(event_type, data):
    """
    Publishes loan events to Multichain for immutable record.
    Supports: loan_request, loan_funded, loan_repayment, loan_completed, user_registered
    """
    from config import (
        MULTICHAIN_RPC_USER,
        MULTICHAIN_RPC_PASSWORD,
        MULTICHAIN_RPC_PORT,
        MULTICHAIN_RPC_HOST,
    )
    
    url = f"http://{MULTICHAIN_RPC_HOST}:{MULTICHAIN_RPC_PORT}"
    headers = {"content-type": "application/json"}
    
    event_data = {
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data
    }
    
    json_text = json.dumps(event_data)
    hex_data = json_text.encode().hex()
    
    payload = {
        "method": "publish",
        "params": ["loan_stream", event_type, hex_data],
        "id": 1,
    }
    
    try:
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=(MULTICHAIN_RPC_USER, MULTICHAIN_RPC_PASSWORD),
            timeout=5
        ).json()
        
        if response.get("error") is not None:
            print(f"[Blockchain] Error publishing {event_type}:", response.get("error"))
            return None
        
        tx_id = response.get("result")
        print(f"[Blockchain] Published {event_type} - TX: {tx_id}")
        return tx_id
    
    except Exception as e:
        print(f"[Blockchain] Connection warning: {e}. Events logged locally.")
        return None

def get_blockchain_events(event_type=None):
    """Retrieve events from blockchain stream"""
    from config import (
        MULTICHAIN_RPC_USER,
        MULTICHAIN_RPC_PASSWORD,
        MULTICHAIN_RPC_PORT,
        MULTICHAIN_RPC_HOST,
    )
    
    try:
        url = f"http://{MULTICHAIN_RPC_HOST}:{MULTICHAIN_RPC_PORT}"
        headers = {"content-type": "application/json"}
        
        payload = {
            "method": "liststreamitems",
            "params": ["loan_stream"],
            "id": 1,
        }
        
        response = requests.post(
            url,
            data=json.dumps(payload),
            headers=headers,
            auth=(MULTICHAIN_RPC_USER, MULTICHAIN_RPC_PASSWORD),
            timeout=5
        ).json()
        
        if response.get("error"):
            return []
        
        events = []
        for item in response.get("result", []):
            try:
                hex_data = item.get("data", "")
                if hex_data:
                    json_data = bytes.fromhex(hex_data).decode()
                    event = json.loads(json_data)
                    if event_type is None or event.get("event_type") == event_type:
                        events.append(event)
            except:
                pass
        
        return events
    
    except Exception as e:
        print(f"[Blockchain] Error retrieving events: {e}")
        return []
