#!/usr/bin/env python3

import sys
import time
from pymongo import MongoClient

def watch_primary(node="mongo2"):
    """Watch for primary changes with timestamps"""

    uri = f"mongodb://{node}:27017/?replicaSet=rs0&retryWrites=true"
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    try:
        client.admin.command("hello")
        print(f"Connected to {node}")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    last_primary = None
    start_time = time.time()

    while True:
        try:
            result = client.admin.command("hello")
            current_primary = result.get("primary", "None")

            if current_primary != last_primary:
                elapsed = time.time() - start_time
                print(f"[{elapsed:.3f}s] PRIMARY CHANGE: {last_primary} -> {current_primary}")
                last_primary = current_primary

            time.sleep(0.3)
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[{elapsed:.3f}s] ERROR: {e}")
            time.sleep(0.3)

if __name__ == "__main__":
    node = sys.argv[1] if len(sys.argv) > 1 else "mongo2"
    watch_primary(node)
