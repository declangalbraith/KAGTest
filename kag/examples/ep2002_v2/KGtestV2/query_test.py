# -*- coding: utf-8 -*-
"""向量召回 + 图谱遍历 的最小测试。"""
import os
import sys
import requests
from neo4j import GraphDatabase

NS = "KGtestV2"
NEO4J_URI = "bolt://106.13.174.178:17688"
NEO4J_AUTH = ("neo4j", "neo4j@openspg")
NEO4J_DB = "kgtestv2"
EMBED_API = "https://api.siliconflow.cn/v1/embeddings"
EMBED_KEY = "sk-yrwobvrcxtpyxaqecbqqkqoacxcxpexeiteyywznyiebavng"
EMBED_MODEL = "BAAI/bge-m3"


def embed(text):
    r = requests.post(
        EMBED_API,
        headers={"Authorization": f"Bearer {EMBED_KEY}",
                 "Content-Type": "application/json"},
        json={"model": EMBED_MODEL, "input": [text]},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["data"][0]["embedding"]


def cosine_search(question, top_k=5):
    qv = embed(question)
    cy = """
    MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH $ns)
      AND n.name_vector IS NOT NULL
    WITH n, gds.similarity.cosine(n.name_vector, $qv) AS score
    RETURN labels(n)[0] AS type, n.name AS name, score
    ORDER BY score DESC LIMIT $k
    """
    # 如果没装 GDS 插件，用纯 Cypher 算余弦：
    cy_pure = """
    MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH $ns)
      AND n.name_vector IS NOT NULL
    WITH n,
         reduce(s=0.0, i IN range(0, size(n.name_vector)-1) | s + n.name_vector[i] * $qv[i]) AS dot,
         sqrt(reduce(s=0.0, x IN n.name_vector | s + x*x)) AS na,
         sqrt(reduce(s=0.0, x IN $qv | s + x*x)) AS nb
    RETURN labels(n)[0] AS type, n.name AS name, dot/(na*nb) AS score
    ORDER BY score DESC LIMIT $k
    """
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    with driver.session(database=NEO4J_DB) as ses:
        try:
            rows = ses.run(cy, ns=f"{NS}.", qv=qv, k=top_k).data()
        except Exception:
            rows = ses.run(cy_pure, ns=f"{NS}.", qv=qv, k=top_k).data()
    driver.close()
    return rows


if __name__ == "__main__":
    questions = [
        "活塞销气孔",
        "EP2002阀压力超差",
        "深圳14号线故障车辆",
        "调节器纠正措施",
    ]
    for q in questions:
        print(f"\n问题: {q}")
        for r in cosine_search(q, top_k=5):
            print(f"  {r['score']:.3f}  {r['type']:30s}  {r['name']}")
