from neo4j import GraphDatabase

NEO4J_URI = "bolt://106.13.174.178:17688"
NEO4J_AUTH = ("neo4j", "neo4j@openspg")
NEO4J_DB = "kgtestv2"
TARGET_DIM = 1024

driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
with driver.session(database=NEO4J_DB) as ses:
    # 1. 列出所有维度不等于目标值的 VECTOR 索引
    indexes = ses.run("""
        SHOW INDEXES YIELD name, type, labelsOrTypes, properties, options
        WHERE type = 'VECTOR'
        RETURN name,
               labelsOrTypes[0] AS label,
               properties[0]    AS prop,
               options.indexConfig.`vector.dimensions`        AS dim,
               options.indexConfig.`vector.similarity_function` AS sim
    """).data()

    print(f"共发现 {len(indexes)} 个 VECTOR 索引：")
    for idx in indexes:
        flag = "OK" if idx['dim'] == TARGET_DIM else "需重建"
        print(f"  [{flag}] {idx['name']}  label={idx['label']}  prop={idx['prop']}  dim={idx['dim']}")

    todo = [i for i in indexes if i['dim'] != TARGET_DIM]
    print(f"\n待重建为 {TARGET_DIM} 维: {len(todo)} 个\n")

    if not todo:
        print("无需重建。")
    else:
        for idx in todo:
            name  = idx['name']
            label = idx['label']
            prop  = idx['prop']
            sim   = idx['sim'] or 'cosine'

            # 删除旧索引
            try:
                ses.run(f"DROP INDEX `{name}`")
                print(f"  删除: {name}")
            except Exception as e:
                print(f"  删除失败 {name}: {e}")
                continue

            # 创建新的 1024 维索引
            try:
                cy = f"""
                CREATE VECTOR INDEX `{name}` IF NOT EXISTS
                FOR (n:`{label}`) ON (n.`{prop}`)
                OPTIONS {{indexConfig: {{
                    `vector.dimensions`: {TARGET_DIM},
                    `vector.similarity_function`: '{sim}'
                }}}}
                """
                ses.run(cy)
                print(f"  创建: {name}  ({TARGET_DIM} dim, {sim})")
            except Exception as e:
                print(f"  创建失败 {name}: {e}")

    # 3. 重建后再列一次，确认所有索引都是 1024 维
    print("\n重建后状态：")
    after = ses.run("""
        SHOW INDEXES YIELD name, type, state, populationPercent, options
        WHERE type = 'VECTOR'
        RETURN name, state, populationPercent,
               options.indexConfig.`vector.dimensions` AS dim
        ORDER BY name
    """).data()
    for r in after:
        print(f"  {r['name']:60s} dim={r['dim']}  state={r['state']}  pop={r['populationPercent']}%")

driver.close()
