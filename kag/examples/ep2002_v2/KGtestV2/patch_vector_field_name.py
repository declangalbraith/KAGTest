from neo4j import GraphDatabase

NEO4J_URI = "bolt://106.13.174.178:17688"
NEO4J_AUTH = ("neo4j", "neo4j@openspg")
NEO4J_DB = "kgtestv2"

driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
with driver.session(database=NEO4J_DB) as ses:
    r1 = ses.run("""
        MATCH (n) WHERE n.name_vector IS NOT NULL AND n.`_name_vector` IS NULL
        SET n.`_name_vector` = n.name_vector
        RETURN count(n) AS cnt
    """).single()
    print(f"复制 _name_vector: {r1['cnt']} 条")

    r2 = ses.run("""
        MATCH (n) WHERE n.content_vector IS NOT NULL AND n.`_content_vector` IS NULL
        SET n.`_content_vector` = n.content_vector
        RETURN count(n) AS cnt
    """).single()
    print(f"复制 _content_vector: {r2['cnt']} 条")

driver.close()
