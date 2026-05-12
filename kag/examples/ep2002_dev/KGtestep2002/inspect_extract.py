import sqlite3, pickle, os

db = "ckpt/SchemaConstraintExtractor/cache.db"
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT rowid, key, value FROM Cache ORDER BY rowid")
rows = cur.fetchall()

total_nodes = 0
labels_count = {}

for rowid, key, value in rows:
    if value is None:
        continue
    try:
        data = pickle.loads(value)
    except Exception as e:
        print(f"row {rowid}: unpickle error: {e}")
        continue
    
    # data 是 list of SubGraph
    if isinstance(data, list):
        for sg in data:
            nodes = getattr(sg, "nodes", [])
            for n in nodes:
                lbl = getattr(n, "label", "?")
                name = getattr(n, "name", "?")
                labels_count[lbl] = labels_count.get(lbl, 0) + 1
                total_nodes += 1
                if total_nodes <= 30:
                    print(f"row{rowid}: label={lbl}, name={name[:60]}")

print(f"\n=== Summary ===")
print(f"Total rows: {len(rows)}")
print(f"Total nodes: {total_nodes}")
print(f"Labels distribution:")
for lbl, cnt in sorted(labels_count.items(), key=lambda x: -x[1]):
    print(f"  {lbl}: {cnt}")
conn.close()