import json
import os
import time
import uuid
from datetime import datetime

import pymysql

try:
    import redis
except ImportError:  # pragma: no cover - cache is optional at runtime
    redis = None


class RecipeStorage:

    def __init__(self):
        self.write_host = os.getenv("DB_WRITE_HOST", os.getenv("DB_HOST", "localhost"))
        self.write_port = int(os.getenv("DB_WRITE_PORT", os.getenv("DB_PORT", "3307")))
        self.read_host = os.getenv("DB_READ_HOST", self.write_host)
        self.read_port = int(os.getenv("DB_READ_PORT", os.getenv("DB_PORT", str(self.write_port))))
        self.user = os.getenv("DB_USER", "root")
        self.password = os.getenv("DB_PASSWORD", "rootpass")
        self.database = os.getenv("DB_NAME", "recipes")
        self.cache_enabled = False
        self.cache_ttl = int(os.getenv("CACHE_TTL_SECONDS", "30"))
        self.cache_prefix = os.getenv("CACHE_KEY_PREFIX", "recipes")
        self._connections = {"write": None, "read": None}
        self._cache = None
        self._init_cache()
        self._init_db()

    def _init_cache(self):
        cache_url = os.getenv("CACHE_URL", "redis://localhost:6379/0")
        if redis is None:
            print("  [CACHE] Redis no disponible, cache deshabilitado")
            return
        try:
            self._cache = redis.from_url(cache_url, decode_responses=True)
            self._cache.ping()
            self.cache_enabled = True
            print(f"  [CACHE] Conectado a Redis en {cache_url}")
        except Exception as exc:
            self._cache = None
            print(f"  [CACHE] Redis no disponible, cache deshabilitado: {exc}")

    def _connect(self, mode: str = "read"):
        host = self.read_host if mode == "read" else self.write_host
        port = self.read_port if mode == "read" else self.write_port
        conn = self._connections[mode]
        if conn is None or not conn.open:
            try:
                conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                )
            except Exception:
                if mode == "read" and (host != self.write_host or port != self.write_port):
                    conn = pymysql.connect(
                        host=self.write_host,
                        port=self.write_port,
                        user=self.user,
                        password=self.password,
                        database=self.database,
                        charset="utf8mb4",
                        cursorclass=pymysql.cursors.DictCursor,
                    )
                else:
                    raise
            self._connections[mode] = conn
        return conn

    def _cache_key_all(self):
        return f"{self.cache_prefix}:all"

    def _cache_key_one(self, recipe_id: str):
        return f"{self.cache_prefix}:{recipe_id}"

    def _cache_get(self, key: str):
        if not self.cache_enabled or self._cache is None:
            return None
        try:
            return self._cache.get(key)
        except Exception:
            self.cache_enabled = False
            return None

    def _cache_set(self, key: str, value: str):
        if not self.cache_enabled or self._cache is None:
            return
        try:
            self._cache.setex(key, self.cache_ttl, value)
        except Exception:
            self.cache_enabled = False

    def _cache_delete(self, *keys: str):
        if not self.cache_enabled or self._cache is None or not keys:
            return
        try:
            self._cache.delete(*keys)
        except Exception:
            self.cache_enabled = False

    def _serialize_row(self, row: dict) -> dict:
        row["tokens"] = json.loads(row["tokens"])
        row["sintaxis"] = json.loads(row["sintaxis"])
        timestamp = row.get("timestamp")
        if timestamp is not None and hasattr(timestamp, "isoformat"):
            row["timestamp"] = timestamp.isoformat()
        elif timestamp is not None:
            row["timestamp"] = str(timestamp)
        return row

    def _init_db(self):
        for attempt in range(30):
            try:
                conn = pymysql.connect(
                    host=self.write_host,
                    port=self.write_port,
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
                print(f"  [DB] Conectado a MariaDB primaria en {self.write_host}:{self.write_port}")
                return
            except Exception as e:
                print(f"  [DB] Esperando MariaDB ({attempt+1}/30): {e}")
                time.sleep(2)
        raise RuntimeError(f"No se pudo conectar a MariaDB primaria en {self.write_host}:{self.write_port}")

    def save(self, source: str, tokens: list, sintaxis: dict, recipe_id: str | None = None) -> dict:
        recipe_id = recipe_id or str(uuid.uuid4())[:8]
        now = datetime.now()
        nodo = os.environ.get("NODE_ROLE", "unknown")
        conn = self._connect("write")
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO recipes (id, entrada, tokens, sintaxis, timestamp, nodo) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (recipe_id, source, json.dumps(tokens), json.dumps(sintaxis), now, nodo),
            )
        conn.commit()
        record = {
            "id": recipe_id,
            "entrada": source,
            "tokens": tokens,
            "sintaxis": sintaxis,
            "timestamp": now.isoformat(),
            "nodo": nodo,
        }
        cached_all = self._cache_get(self._cache_key_all())
        if cached_all:
            try:
                recipes = json.loads(cached_all)
                recipes = [item for item in recipes if item.get("id") != recipe_id]
                recipes.append(record)
                recipes.sort(key=lambda item: item.get("timestamp") or "")
                self._cache_set(self._cache_key_all(), json.dumps(recipes, ensure_ascii=False))
            except Exception:
                self._cache_delete(self._cache_key_all())
        else:
            self._cache_delete(self._cache_key_all())
        self._cache_set(self._cache_key_one(recipe_id), json.dumps(record, ensure_ascii=False))
        return record

    def get_all(self) -> list:
        cached = self._cache_get(self._cache_key_all())
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                self._cache_delete(self._cache_key_all())

        conn = self._connect("read")
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM recipes ORDER BY timestamp ASC")
            rows = cur.fetchall()
        results = [self._serialize_row(r) for r in rows]
        self._cache_set(self._cache_key_all(), json.dumps(results, ensure_ascii=False))
        for recipe in results:
            self._cache_set(self._cache_key_one(recipe["id"]), json.dumps(recipe, ensure_ascii=False))
        return results

    def get_by_id(self, recipe_id: str) -> dict | None:
        cached = self._cache_get(self._cache_key_one(recipe_id))
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                self._cache_delete(self._cache_key_one(recipe_id))

        conn = self._connect("read")
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM recipes WHERE id = %s", (recipe_id,))
            r = cur.fetchone()
        if r:
            result = self._serialize_row(r)
            self._cache_set(self._cache_key_one(recipe_id), json.dumps(result, ensure_ascii=False))
            return result
        return None
