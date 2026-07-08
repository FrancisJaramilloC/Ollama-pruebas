import json
import os
import threading
import requests

from src.storage import RecipeStorage


class RecipeSync:
    """
    Sincronizacion de recetas entre nodo principal y replica.
    El nodo principal ejecuta push hacia la replica.
    """

    def __init__(self, storage: RecipeStorage):
        self.storage = storage
        self.role = os.environ.get("NODE_ROLE", "replica")
        self.replica_url = os.environ.get("REPLICA_URL", "http://nodo-replica:8000")
        self.main_url = os.environ.get("MAIN_URL", "http://nodo-principal:8000")

    def push_to_replica(self, record: dict) -> bool:
        if self.role != "main":
            return False
        try:
            resp = requests.post(
                f"{self.replica_url}/internal/recipes",
                json=record,
                timeout=5
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def pull_from_main(self) -> list:
        if self.role != "replica":
            return []
        try:
            resp = requests.get(f"{self.main_url}/internal/recipes", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except requests.RequestException:
            pass
        return []

    def sync_replica(self):
        if self.role != "replica":
            return
        remote = self.pull_from_main()
        local_ids = {r["id"] for r in self.storage.get_all()}
        synced = 0
        for record in remote:
            if record["id"] not in local_ids:
                self.storage.save(
                    record["entrada"],
                    record["tokens"],
                    record["sintaxis"],
                    recipe_id=record["id"],
                )
                synced += 1
        if synced > 0:
            print(f"  [SYNC] Replica sincronizada: {synced} recetas nuevas")

    def start_auto_sync(self, interval: int = 30):
        if self.role != "replica":
            return
        def _loop():
            while True:
                threading.Event().wait(interval)
                self.sync_replica()
        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        print(f"  [SYNC] Auto-sync cada {interval}s (rol={self.role})")
