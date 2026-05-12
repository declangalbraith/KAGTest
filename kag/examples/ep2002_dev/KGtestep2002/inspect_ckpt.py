import sqlite3
import json
import os

ckpt_dir = "ckpt"
for sub in ["SchemaConstraintExtractor", "KGWriter", "BatchVectorizer"]:
    db = os.path.join(ckpt_dir, sub, "cache.db")
    if not os.path.exists(db):
        print(f"[{sub}] not found")
        continue
    print(f"\n========== {sub} ==========")
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    # 列出表
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cur.fetchone()[0]
        print(f"  Table {t}: {cnt} rows")
        # 看前 1 行的列
        cur.execute(f"SELECT * FROM {t} LIMIT 1")
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        if row:
            print(f"  Columns: {cols}")
            for col, val in zip(cols, row):
                v = str(val)
                if len(v) > 500:
                    v = v[:500] + "...(truncated)"
                print(f"    {col}: {v}")
    conn.close()
