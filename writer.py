#!/usr/bin/env python3

import sys
import time
from datetime import datetime
from pymongo import MongoClient
from pymongo.errors import PyMongoError

def main():
    if len(sys.argv) < 2:
        uri = "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0&retryWrites=true"
    else:
        uri = sys.argv[1]

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client.census
    collection = db.heartbeat

    successful = 0
    failed = 0
    start_time = time.time()

    try:
        collection.drop()
        print("[INFO] Collection reset")

        i = 0
        while True:
            try:
                timestamp = datetime.utcnow().isoformat()
                hello = client.admin.command("hello")
                primary = hello.get("primary", "unknown")

                doc = {
                    "_id": i,
                    "timestamp": timestamp,
                    "primary_at_write": primary,
                    "sequence": i
                }

                collection.insert_one(doc)
                elapsed = time.time() - start_time
                print(f"[{elapsed:7.3f}s] OK     {timestamp} primary={primary}")
                successful += 1
                i += 1

            except PyMongoError as e:
                elapsed = time.time() - start_time
                error_code = getattr(e, 'code', 'N/A')
                print(f"[{elapsed:7.3f}s] FAIL   {datetime.utcnow().isoformat()} {type(e).__name__} code={error_code}")
                failed += 1

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        elapsed = time.time() - start_time
        real_count = collection.count_documents({})
        print(f"\n--- FINAL STATS ---")
        print(f"Elapsed: {elapsed:.3f}s")
        print(f"Successful writes (reported): {successful}")
        print(f"Failed writes: {failed}")
        print(f"Real collection count: {real_count}")
        print(f"Discrepancy: {successful - real_count}")
        client.close()

if __name__ == "__main__":
    main()
