# -*- coding: utf-8 -*-
"""
对 Neo4j 中所有 KGtestV2.* 节点的 name 字段做向量化，
写入 name_vector 属性（维度 1024，对应 bge-m3）。
"""
import os
import sys
import time
import requests
from neo4j import GraphDatabase

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

NS = "KGtestV2"
NEO4J_URI = "bolt://106.13.174.178:17688"
NEO4J_AUTH = ("neo4j", "neo4j@openspg")
NEO4J_DB = "kgtestv2"

EMBED_API = "https://api.siliconflow.cn/v1/embeddings"
EMBED_KEY = "sk-yrwobvrcxtpyxaqecbqqkqoacxcxpexeiteyywznyiebavng"   # 同 yaml 里的 key
EMBED_MODEL = "BAAI/bge-m3"

BATCH = 16


def embed(texts):
    """调 SiliconFlow embedding，一次 batch 返回 List[List[float]]。"""
    r = requests.post(
        EMBED_API,
        headers={"Authorization": f"Bearer {EMBED_KEY}",
                 "Content-Type": "application/json"},
        json={"model": EMBED_MODEL, "input": texts},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()["data"]
    return [d["embedding"] for d in sorted(data, key=lambda x: x["index"])]


driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
with driver.session(database=NEO4J_DB) as ses:
    nodes = ses.run(
        "MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH $ns) "
        "  AND n.name_vector IS NULL "
        "RETURN id(n) AS nid, n.name AS name", ns=f"{NS}."
    ).data()
print(f"待向量化节点: {len(nodes)}")

written = 0
for i in range(0, len(nodes), BATCH):
    batch = nodes[i:i+BATCH]
    texts = [str(n["name"]) for n in batch]
    try:
        vecs = embed(texts)
    except Exception as e:
        print(f"  embedding 失败 batch={i}: {e}")
        time.sleep(2)
        continue
    with driver.session(database=NEO4J_DB) as ses:
        for n, v in zip(batch, vecs):
            ses.run("MATCH (n) WHERE id(n)=$nid SET n.name_vector=$v",
                    nid=n["nid"], v=v)
            written += 1
    print(f"  进度 {written}/{len(nodes)}")
    time.sleep(0.3)

print(f"\n完成: 写入 {written} 个 name_vector")

# 也给 Chunk 的 content 字段建向量（如果存在 content 字段）
with driver.session(database=NEO4J_DB) as ses:
    chunks = ses.run(
        f"MATCH (c:`{NS}.Chunk`) WHERE c.content IS NOT NULL AND c.content_vector IS NULL "
        "RETURN id(c) AS nid, c.content AS content"
    ).data()
print(f"\n待向量化 Chunk: {len(chunks)}")

c_written = 0
for i in range(0, len(chunks), BATCH):
    batch = chunks[i:i+BATCH]
    texts = [str(c["content"])[:2000] for c in batch]   # bge-m3 最长 8K，这里截断保险
    try:
        vecs = embed(texts)
    except Exception as e:
        print(f"  embedding 失败 batch={i}: {e}")
        continue
    with driver.session(database=NEO4J_DB) as ses:
        for c, v in zip(batch, vecs):
            ses.run("MATCH (n) WHERE id(n)=$nid SET n.content_vector=$v",
                    nid=c["nid"], v=v)
            c_written += 1
    time.sleep(0.3)

# ============ 后处理：同步到 OpenSPG 服务端读取的字段 / 标签 ============
print("\n[后处理] 同步 _name_vector / _content_vector 字段并补 Entity 标签...")
with driver.session(database=NEO4J_DB) as ses:
    # 1. 复制 name_vector -> _name_vector（覆盖式，确保新增节点同步）
    cnt1 = ses.run("""
        MATCH (n) WHERE n.name_vector IS NOT NULL
        SET n.`_name_vector` = n.name_vector
        RETURN count(n) AS cnt
    """).single()['cnt']
    print(f"  _name_vector 已同步: {cnt1} 个节点")

    # 2. 复制 content_vector -> _content_vector
    cnt2 = ses.run("""
        MATCH (n) WHERE n.content_vector IS NOT NULL
        SET n.`_content_vector` = n.content_vector
        RETURN count(n) AS cnt
    """).single()['cnt']
    print(f"  _content_vector 已同步: {cnt2} 个节点")

    # 3. 给 KGtestV2.* 节点补 Entity 父标签（用于 _entity_name_vector_index 召回）
    cnt3 = ses.run("""
        MATCH (n) WHERE labels(n)[0] STARTS WITH 'KGtestV2.'
        AND NOT n:Entity
        SET n:Entity
        RETURN count(n) AS cnt
    """).single()['cnt']
    print(f"  Entity 父标签已补: {cnt3} 个节点")

    # 4. 验证：Entity 标签下应有的向量字段填充率
    stat = ses.run("""
        MATCH (n:Entity)
        RETURN count(n) AS total,
               count(n.`_name_vector`) AS has_name_vec
    """).single()
    print(f"  Entity 总数={stat['total']}, _name_vector 已填充={stat['has_name_vec']}")
print(f"完成: 写入 {c_written} 个 content_vector")
print("[后处理] 完成。\n")

driver.close()
