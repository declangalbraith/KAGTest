# -*- coding: utf-8 -*-
"""
按 reportNo 合并重复的 EightDReport 节点。

流程：
  1. 找出所有 reportNo 相同的 EightDReport 节点组（size >= 2）
  2. 按 score() 选信息量最大的节点为主节点 (KEEP)，其余为碎片 (DROP)
  3. BACKFILL：把 DROP 上有、KEEP 上没有的字段补到 KEEP
  4. apoc.refactor.mergeNodes 合并（properties: 'discard'，保留 KEEP）
  5. 清掉合并后主节点的 name_vector / _name_vector / content_vector / _content_vector，
     让后续 vectorize_nodes.py 自动重新算（增量）

依赖：Neo4j APOC 插件（OpenSPG 镜像默认带）
"""

from neo4j import GraphDatabase

NEO4J_URI  = "bolt://106.13.174.178:17688"
NEO4J_USER = "neo4j"
NEO4J_PWD  = "neo4j@openspg"
NEO4J_DB   = "kgtestv2"

LABEL = "KGtestV2.EightDReport"
DRY_RUN = False   # ← 先 True 看日志，确认无误后改 False 再跑一次


# ---------- Cypher ----------
# 显式返回 elementId 列表和属性 map 列表，避免 driver 把 Node 自动展开成 dict 后丢失 element_id
FIND_GROUPS = f"""
MATCH (r:`{LABEL}`)
WHERE r.reportNo IS NOT NULL AND trim(r.reportNo) <> ''
WITH trim(r.reportNo) AS rno, collect(r) AS nodes
WHERE size(nodes) > 1
RETURN rno,
       [n IN nodes | elementId(n)] AS ids,
       [n IN nodes | properties(n)] AS props
"""

BACKFILL_CYPHER = """
MATCH (keep) WHERE elementId(keep) = $keep_id
MATCH (drop) WHERE elementId(drop) IN $drop_ids
WITH keep, drop
UNWIND keys(drop) AS k
WITH keep, drop, k
WHERE drop[k] IS NOT NULL AND drop[k] <> '' AND drop[k] <> []
  AND (keep[k] IS NULL OR keep[k] = '' OR keep[k] = [])
CALL apoc.create.setProperty(keep, k, drop[k]) YIELD node
RETURN count(*) AS filled
"""

MERGE_CYPHER = """
MATCH (keep) WHERE elementId(keep) = $keep_id
MATCH (drop) WHERE elementId(drop) IN $drop_ids
WITH keep, collect(drop) AS drops
CALL apoc.refactor.mergeNodes(
    [keep] + drops,
    {properties: 'discard', mergeRels: true}
) YIELD node
RETURN elementId(node) AS merged_id
"""

CLEAR_VECTOR_CYPHER = """
MATCH (n) WHERE elementId(n) = $keep_id
REMOVE n.name_vector, n.`_name_vector`,
       n.content_vector, n.`_content_vector`
RETURN elementId(n) AS id
"""


# ---------- 评分：挑信息量最大的节点当主节点 ----------
def score(props):
    """props 是 dict（节点属性）"""
    # 排除向量字段，避免它们让 non_empty 虚高
    EXCLUDE_KEYS = {"name_vector", "_name_vector",
                    "content_vector", "_content_vector",
                    "_name_vector_index", "_content_vector_index"}
    non_empty = sum(
        1 for k, v in props.items()
        if k not in EXCLUDE_KEYS and v not in (None, "", [], {})
    )
    name_len = len(props.get("name", "") or "")
    bonus = 0
    for k in ("issueTitle", "ownerName", "ownerRole",
              "d4RootCauseSummary", "d5PermanentCorrectionSummary",
              "d7PreventionSummary", "d8TeamCongratulationsSummary"):
        if props.get(k):
            bonus += 5
    return non_empty * 10 + name_len + bonus


def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PWD))
    with driver.session(database=NEO4J_DB) as sess:
        groups = sess.run(FIND_GROUPS).data()
        print(f"[INFO] 发现 {len(groups)} 组重复的 {LABEL} (按 reportNo)")
        if not groups:
            print("[INFO] 没有需要合并的节点，退出。")
            driver.close()
            return

        total_merged = 0
        total_dropped = 0

        for g in groups:
            rno   = g["rno"]
            ids   = g["ids"]      # List[str]，elementId 列表
            props = g["props"]    # List[dict]，每个节点的属性

            # 组装成 (id, props, score) 三元组并按 score 倒序
            ranked = sorted(
                zip(ids, props),
                key=lambda x: score(x[1]),
                reverse=True
            )
            keep_id, keep_props = ranked[0]
            drops = ranked[1:]    # List[(id, props)]

            print("\n" + "=" * 70)
            print(f"[GROUP] reportNo = {rno}  共 {len(ids)} 个节点")
            for eid, p in ranked:
                tag = "KEEP" if eid == keep_id else "DROP"
                name_preview = (p.get("name", "") or "")[:60]
                print(f"  [{tag}] elementId={eid} "
                      f"score={score(p)} name={name_preview!r}")

            if DRY_RUN:
                print("[DRY_RUN] 跳过实际合并")
                continue

            drop_ids = [eid for eid, _ in drops]

            # 1) BACKFILL：补字段
            filled = sess.run(
                BACKFILL_CYPHER,
                keep_id=keep_id,
                drop_ids=drop_ids,
            ).single()["filled"]
            print(f"  [BACKFILL] 补充 {filled} 个字段到主节点")

            # 2) MERGE：合并节点 + 关系
            merged_id = sess.run(
                MERGE_CYPHER,
                keep_id=keep_id,
                drop_ids=drop_ids,
            ).single()["merged_id"]
            print(f"  [MERGE] 完成，主节点 elementId={merged_id}, "
                  f"删除 {len(drop_ids)} 个碎片")

            # 3) CLEAR VECTOR：清掉主节点向量字段
            sess.run(CLEAR_VECTOR_CYPHER, keep_id=merged_id)
            print(f"  [CLEAR_VEC] 已清空主节点向量字段（待 vectorize_nodes.py 重算）")

            total_merged += 1
            total_dropped += len(drop_ids)

        print("\n" + "=" * 70)
        print(f"[DONE] 处理 {total_merged} 组，删除 {total_dropped} 个碎片节点")

    driver.close()


if __name__ == "__main__":
    main()
