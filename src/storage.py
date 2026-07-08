import json
import os
import uuid
import time
import pymysql
from datetime import datetime


class RecipeStorage:

    def __init__(self):
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = int(os.getenv("DB_PORT", "3307"))
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "rootpass")
        self.database = os.getenv("DB_NAME", "recipes")
        self._conn = None
        self._init_db()

    def _connect(self):
        if self._conn is None or not self._conn.open:
            self._conn = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
        return self._conn

    def _init_db(self):
        for attempt in range(30):
            try:
                conn = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    charset="utf8mb4",
                )
                with conn.cursor() as cur:
                    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.database}`")
                    cur.execute(f"USE `{self.database}`")
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS recipes (
                            id VARCHAR(8) PRIMARY KEY,
                            entrada TEXT NOT NULL,
                            tokens JSON NOT NULL,
                            sintaxis JSON NOT NULL,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            nodo VARCHAR(20) DEFAULT 'unknown'
                        )
                    """)
                conn.close()
                print(f"  [DB] Conectado a MariaDB en {self.host}:{self.port}")
                return
            except Exception as e:
                print(f"  [DB] Esperando MariaDB ({attempt+1}/30): {e}")
                time.sleep(2)
        raise RuntimeError(f"No se pudo conectar a MariaDB en {self.host}:{self.port}")

    def save(self, source: str, tokens: list, sintaxis: dict, recipe_id: str | None = None) -> dict:
        recipe_id = recipe_id or str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        nodo = os.environ.get("NODE_ROLE", "unknown")
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO recipes (id, entrada, tokens, sintaxis, timestamp, nodo) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (recipe_id, source, json.dumps(tokens), json.dumps(sintaxis), now, nodo),
            )
        conn.commit()
        return {
            "id": recipe_id,
            "entrada": source,
            "tokens": tokens,
            "sintaxis": sintaxis,
            "timestamp": now,
            "nodo": nodo,
        }

    def get_all(self) -> list:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM recipes ORDER BY timestamp ASC")
            rows = cur.fetchall()
        results = []
        for r in rows:
            r["tokens"] = json.loads(r["tokens"])
            r["sintaxis"] = json.loads(r["sintaxis"])
            r["timestamp"] = r["timestamp"].isoformat() if r.get("timestamp") else None
            results.append(r)
        return results

    def get_by_id(self, recipe_id: str) -> dict | None:
        conn = self._connect()
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM recipes WHERE id = %s", (recipe_id,))
            r = cur.fetchone()
        if r:
            r["tokens"] = json.loads(r["tokens"])
            r["sintaxis"] = json.loads(r["sintaxis"])
            r["timestamp"] = r["timestamp"].isoformat()
            return r
        return None
