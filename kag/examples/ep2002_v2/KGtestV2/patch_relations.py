# -*- coding: utf-8 -*-
"""
读取最新的 _llm_dump/*_relations.json，
把五元组按命名边写进 Neo4j。
节点 name 在 Neo4j 里是小写并带双引号包裹，需要 normalize 后比对。
"""
import os
import json
import glob
import re
from neo4j import GraphDatabase

NS = "KGtestV2"
NEO4J_URI = "bolt://106.13.174.178:17688"
NEO4J_AUTH = ("neo4j", "neo4j@openspg")
NEO4J_DB = "kgtestv2"

# 读取最近 N 个 relations.json（一个文档可能切多 chunk → 多个 json）
N_LATEST = 10


def norm(s):
    """统一为小写并去掉所有空白、引号、常见标点、全角/半角括号，用于模糊匹配 name。"""
    if s is None:
        return ""
    s = str(s).lower()
    # 全角 → 半角
    s = s.replace("（", "(").replace("）", ")")
    s = s.replace("，", ",").replace("。", ".")
    s = s.replace("：", ":").replace("；", ";")
    s = s.replace("　", " ")
    # 去掉空白、引号、括号、连字符、下划线、常见标点
    s = re.sub(r'[\s"\'`()【】《》<>_\-—,.，。、:：;；!！?？]', "", s)
    return s


def find_actual(label, raw_name, node_index, min_prefix_len=6):
    """先精确 norm 匹配；失败时回退到 prefix/包含匹配。"""
    target = norm(raw_name)
    actual = node_index.get((label, target))
    if actual is not None:
        return actual
    if len(target) < min_prefix_len:
        return None
    # 包含匹配（target 是 key 的子串，或反之）
    candidates = [
        (k_norm, real)
        for (lbl, k_norm), real in node_index.items()
        if lbl == label and (target in k_norm or k_norm in target)
    ]
    if not candidates:
        return None
    # 取最短的，通常是最贴近的
    candidates.sort(key=lambda x: len(x[0]))
    return candidates[0][1]


def main():
    # 找最近 N_LATEST 个 relations.json
    dump_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "builder", "prompt", "_llm_dump",
    )
    all_files = sorted(
        glob.glob(os.path.join(dump_dir, "*_relations.json")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not all_files:
        raise SystemExit("找不到 relations.json")

    files = all_files[:N_LATEST]
    files.sort(key=os.path.getmtime)  # 按时间从早到晚处理
    print(f"读取最近 {len(files)} 个 relations 文件:")
    triples = []
    for f in files:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
            triples.extend(data)
            print(f"  - {os.path.basename(f)}  ({os.path.getsize(f)} bytes, {len(data)} 条)")
    print(f"\n合并后共 {len(triples)} 条三元组待写入\n")

    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)

    # 第 1 步：把数据库里所有 KGtestV2.* 节点的 (label, name) 捞出来，
    #         在 Python 里建 normalize 索引
    print(f"扫描数据库 {NEO4J_DB} 中的节点...")
    node_index = {}  # (label, normalized_name) -> 真实 name
    with driver.session(database=NEO4J_DB) as ses:
        rows = ses.run(
            "MATCH (n) WHERE any(l IN labels(n) WHERE l STARTS WITH $ns) "
            "RETURN labels(n)[0] AS label, n.name AS name",
            ns=f"{NS}.",
        )
        for r in rows:
            label = r["label"].split(".", 1)[-1]  # 'KGtestV2.EightDReport' -> 'EightDReport'
            actual = r["name"]
            if actual:
                node_index[(label, norm(actual))] = actual
    print(f"共扫描到 {len(node_index)} 个节点\n")

    # 第 2 步：写入关系
    written = skipped = 0
    miss = []
    with driver.session(database=NEO4J_DB) as ses:
        for triple in triples:
            # 兼容五元组 / 三元组(对象) 两种格式
            if isinstance(triple, dict):
                s_name = triple.get("subject") or triple.get("s")
                s_label = triple.get("subject_type") or triple.get("s_type")
                predicate = triple.get("predicate") or triple.get("p")
                o_name = triple.get("object") or triple.get("o")
                o_label = triple.get("object_type") or triple.get("o_type")
            else:
                # 列表格式: [s_name, s_label, predicate, o_name, o_label]
                if len(triple) < 5:
                    skipped += 1
                    continue
                s_name, s_label, predicate, o_name, o_label = triple[:5]

            s_actual = find_actual(s_label, s_name, node_index)
            o_actual = find_actual(o_label, o_name, node_index)

            if s_actual is None or o_actual is None:
                skipped += 1
                if len(miss) < 15:
                    miss.append(
                        f"{s_label}:{s_name!r} (找到={s_actual is not None}) "
                        f"-[{predicate}]-> "
                        f"{o_label}:{o_name!r} (找到={o_actual is not None})"
                    )
                continue

            cy = (
                f"MATCH (a:`{NS}.{s_label}` {{name: $s}}), "
                f"(b:`{NS}.{o_label}` {{name: $o}}) "
                f"MERGE (a)-[r:`{predicate}`]->(b) RETURN count(r) AS c"
            )
            try:
                rec = ses.run(cy, s=s_actual, o=o_actual).single()
                if rec and rec["c"] > 0:
                    written += 1
                else:
                    skipped += 1
            except Exception as e:
                skipped += 1
                print(f"  错误: {e}")

    print(f"\n完成: 写入 {written}, 跳过 {skipped}")
    if miss:
        print("\n跳过示例(节点不存在或类型不匹配):")
        for x in miss:
            print(f"  - {x}")
    driver.close()


if __name__ == "__main__":
    main()
