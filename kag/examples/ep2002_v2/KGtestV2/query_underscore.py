import requests
from neo4j import GraphDatabase

NEO4J_URI = "bolt://106.13.174.178:17688"
NEO4J_AUTH = ("neo4j", "neo4j@openspg")
NEO4J_DB = "kgtestv2"
EMBED_API = "https://api.siliconflow.cn/v1/embeddings"
API_KEY = "sk-yrwobvrcxtpyxaqecbqqkqoacxcxpexeiteyywznyiebavng"

def embed(text):
    r = requests.post(EMBED_API,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": "BAAI/bge-m3", "input": text})
    return r.json()["data"][0]["embedding"]

q = "ep2002有哪些部件"
qv = embed(q)

driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
with driver.session(database=NEO4J_DB) as ses:
    cy = """
    MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH 'KGtestV2.')
      AND n.`_name_vector` IS NOT NULL
    WITH n,
         reduce(s=0.0, i IN range(0, size(n.`_name_vector`)-1) | s + n.`_name_vector`[i] * $qv[i]) AS dot,
         sqrt(reduce(s=0.0, x IN n.`_name_vector` | s + x*x)) AS na,
         sqrt(reduce(s=0.0, x IN $qv | s + x*x)) AS nb
    RETURN labels(n)[0] AS type, n.name AS name, dot/(na*nb) AS score
    ORDER BY score DESC LIMIT 10
    """
    rows = ses.run(cy, qv=qv).data()
    for r in rows:
        print(f"  {r['score']:.3f}  {r['type']:35s} {r['name']}")
driver.close()
