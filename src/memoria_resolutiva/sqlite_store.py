from __future__ import annotations
import sqlite3
from pathlib import Path

from .layers import layer_bits
from .node import digest_payload


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS memories(
  memory_id TEXT PRIMARY KEY,
  payload BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS nodes(
  node_id TEXT PRIMARY KEY,
  layer INTEGER NOT NULL,
  payload BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS occurrences(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  memory_id TEXT NOT NULL,
  layer INTEGER NOT NULL,
  local_time INTEGER NOT NULL,
  node_id TEXT NOT NULL,
  FOREIGN KEY(memory_id) REFERENCES memories(memory_id) ON DELETE CASCADE,
  FOREIGN KEY(node_id) REFERENCES nodes(node_id)
);
CREATE INDEX IF NOT EXISTS idx_occ_node ON occurrences(node_id);
CREATE INDEX IF NOT EXISTS idx_occ_memory_layer_time ON occurrences(memory_id, layer, local_time);
"""


class SQLiteResolutiveMemory:
    def __init__(self, path: str | Path, max_layer: int = 3):
        self.path = str(path)
        self.max_layer = max_layer
        self.db = sqlite3.connect(self.path)
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def _chunks(self, data: bytes, layer: int):
        width = layer_bits(layer) // 8
        for offset in range(0, len(data), width):
            yield offset // width, data[offset:offset + width]

    def add(self, memory_id: str, data: bytes) -> None:
        with self.db:
            self.db.execute("INSERT INTO memories(memory_id,payload) VALUES(?,?)", (memory_id, data))
            for layer in range(self.max_layer + 1):
                for local_time, payload in self._chunks(data, layer):
                    if not payload:
                        continue
                    node_id = digest_payload(payload, layer)
                    self.db.execute(
                        "INSERT OR IGNORE INTO nodes(node_id,layer,payload) VALUES(?,?,?)",
                        (node_id, layer, payload),
                    )
                    self.db.execute(
                        "INSERT INTO occurrences(memory_id,layer,local_time,node_id) VALUES(?,?,?,?)",
                        (memory_id, layer, local_time, node_id),
                    )

    def reconstruct(self, memory_id: str) -> bytes:
        row = self.db.execute("SELECT payload FROM memories WHERE memory_id=?", (memory_id,)).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return bytes(row[0])

    def stats(self) -> dict:
        memories = self.db.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        nodes = self.db.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
        occurrences = self.db.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0]
        per_layer = dict(self.db.execute("SELECT layer,COUNT(*) FROM nodes GROUP BY layer ORDER BY layer"))
        return {"memories": memories, "unique_nodes": nodes, "occurrences": occurrences, "nodes_per_layer": per_layer}
