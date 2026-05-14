# -*- coding: utf-8 -*-
"""
KGtestV2 图谱清洗 + 去重(每次 indexer 跑完后执行)。
功能:
  1. 去掉所有 KGtestV2.* 节点字符串属性外层的 OpenSPG 转义引号
  2. 删除主键字段为占位符/空值的垃圾节点
  3. 按业务主键(或 name)合并同值节点
"""
from neo4j import GraphDatabase

NEO4J_URI  = "bolt://106.13.174.178:17688"
NEO4J_AUTH = ("neo4j", "neo4j@openspg")
NEO4J_DB   = "kgtestv2"

DRY_RUN = False

# (label, 主键字段 或 None 表示按 name 合并)
TARGETS = [
    ("KGtestV2.ProductModel",    "modelCode"),
    ("KGtestV2.ProductInstance", "serialNumber"),
    ("KGtestV2.Installation",    "installationId"),
    ("KGtestV2.EightDReport",    "reportNo"),
    ("KGtestV2.FailureMode",     "modeCode"),
    ("KGtestV2.EventCategory",   "categoryCode"),
    ("KGtestV2.Organization",    "name"),       # 没业务主键,按 name 合并
    ("KGtestV2.BOMPart",         "partNo"),     # 抽取已稳定可按 partNo 合并
    ("KGtestV2.ProductEvent",    "name"),       # eventId 不可靠,按 name 合并
    ("KGtestV2.CauseItem",       "name"),       # causeId 不可靠,按 name 合并
    ("KGtestV2.ActionItem",      "name"),       # actionId 不可靠,按 name 合并
]

PLACEHOLDER_TOKENS = [
    "不明确", "未知", "未提供", "未指定", "未说明", "暂无",
    "N/A", "n/a", "NA", "None", "none", "null", "NULL",
]


def strip_outer_quotes(s):
    if not isinstance(s, str):
        return s
    prev = None
    cur = s.strip()
    while prev != cur:
        prev = cur
        if len(cur) >= 2 and (
            (cur[0] == '"' and cur[-1] == '"') or
            (cur[0] == "'" and cur[-1] == "'") or
            (cur[0] == "“" and cur[-1] == "”")
        ):
            cur = cur[1:-1].strip()
    return cur


def is_invalid_key(s):
    if s is None or s == "":
        return True
    s2 = strip_outer_quotes(s) if isinstance(s, str) else s
    if not s2:
        return True
    return any(tok in str(s2) for tok in PLACEHOLDER_TOKENS)


def clean_label(sess, label, key, dry_run):
    print("\n" + "=" * 70)
    print(f"[{label}] 主键字段={key}")

    # 1) 拉所有节点 + 所有字符串属性
    rows = sess.run(
        f"MATCH (n:`{label}`) "
        f"RETURN elementId(n) AS eid, properties(n) AS props"
    ).data()
    print(f"  节点总数: {len(rows)}")

    # 2) 给每个节点逐属性去引号
    fix_count = 0
    for row in rows:
        eid = row["eid"]
        props = row["props"]
        updates = {}
        for k, v in props.items():
            if isinstance(v, str):
                cleaned = strip_outer_quotes(v)
                if cleaned != v:
                    updates[k] = cleaned
        if updates:
            fix_count += 1
            if not dry_run:
                # 用 SET n += $updates 批量更新
                sess.run(
                    "MATCH (n) WHERE elementId(n)=$eid SET n += $updates",
                    eid=eid, updates=updates,
                )
    print(f"  待去引号的节点: {fix_count}")

    # 3) 删除主键字段无效的节点
    if not dry_run:
        # 先重新拉一次(已经去过引号)
        rows = sess.run(
            f"MATCH (n:`{label}`) "
            f"RETURN elementId(n) AS eid, n.`{key}` AS k"
        ).data()
    delete_count = 0
    to_delete = []
    for row in rows:
        v = row.get("k") if dry_run else row["k"]
        # dry_run 模式下,从原 props 里取(且需先模拟去引号)
        if dry_run:
            raw = next((r["props"].get(key) for r in rows
                        if isinstance(r, dict) and r["eid"] == row["eid"]), None)
            v = strip_outer_quotes(raw) if isinstance(raw, str) else raw
        if is_invalid_key(v):
            to_delete.append(row["eid"])
            delete_count += 1
    print(f"  待删除(主键无效): {delete_count}")
    if not dry_run and to_delete:
        sess.run(
            "MATCH (n) WHERE elementId(n) IN $ids DETACH DELETE n",
            ids=to_delete,
        )

    # 4) 合并同主键的节点
    if not dry_run:
        dups = sess.run(
            f"MATCH (n:`{label}`) WHERE n.`{key}` IS NOT NULL AND n.`{key}` <> '' "
            f"WITH n.`{key}` AS k, collect(n) AS nodes "
            f"WHERE size(nodes) > 1 "
            f"RETURN k, [x IN nodes | elementId(x)] AS ids"
        ).data()
        print(f"  合并组数: {len(dups)}")
        for d in dups:
            ids = d["ids"]
            sess.run(
                "MATCH (n) WHERE elementId(n) IN $ids "
                "WITH collect(n) AS ns "
                "CALL apoc.refactor.mergeNodes(ns, "
                "  {properties:'discard', mergeRels:true}) YIELD node "
                "RETURN node",
                ids=ids,
            )


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    with driver.session(database=NEO4J_DB) as sess:
        for label, key in TARGETS:
            clean_label(sess, label, key, DRY_RUN)
    driver.close()
    print("\n[DONE]")


if __name__ == "__main__":
    main()
