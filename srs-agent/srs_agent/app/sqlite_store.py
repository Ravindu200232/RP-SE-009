"""Durable local SRS storage when a MongoDB service is unavailable."""
import copy
import json
import sqlite3
import threading


class SQLiteStore:
    backend = "sqlite"

    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS documents (row_id INTEGER PRIMARY KEY, collection TEXT NOT NULL, body TEXT NOT NULL)")
        self._db.execute("CREATE INDEX IF NOT EXISTS documents_collection ON documents(collection)")
        self._db.commit()

    def _rows(self, collection, query):
        from .db import _matches
        for row_id, body in self._db.execute("SELECT row_id, body FROM documents WHERE collection=?", (collection,)):
            doc = json.loads(body)
            if _matches(doc, query or {}):
                yield row_id, doc

    async def insert_one(self, collection, doc):
        with self._lock, self._db:
            self._db.execute("INSERT INTO documents(collection, body) VALUES (?, ?)", (collection, json.dumps(doc)))
        return copy.deepcopy(doc)

    async def find_one(self, collection, query):
        with self._lock:
            return next((doc for _, doc in self._rows(collection, query)), None)

    async def find(self, collection, query=None, sort=None, limit=None):
        with self._lock:
            rows = [doc for _, doc in self._rows(collection, query)]
        if sort:
            key, direction = sort
            rows.sort(key=lambda doc: doc.get(key) or "", reverse=direction < 0)
        return rows[:limit] if limit else rows

    async def update_one(self, collection, query, set_fields):
        with self._lock, self._db:
            row = next(self._rows(collection, query), None)
            if row is None:
                return False
            row_id, doc = row
            doc.update(copy.deepcopy(set_fields))
            self._db.execute("UPDATE documents SET body=? WHERE row_id=?", (json.dumps(doc), row_id))
            return True

    async def count(self, collection, query=None):
        with self._lock:
            return sum(1 for _ in self._rows(collection, query))

    async def delete_many(self, collection, query):
        with self._lock, self._db:
            ids = [(row_id,) for row_id, _ in self._rows(collection, query)]
            self._db.executemany("DELETE FROM documents WHERE row_id=?", ids)
            return len(ids)

    async def ping(self):
        return True

    async def close(self):
        with self._lock:
            self._db.close()
