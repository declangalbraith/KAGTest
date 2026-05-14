# -*- coding: utf-8 -*-
"""
两段式 QA(简洁版):
  一、检索证据(每个子任务的核心结论 + 来源)
  二、最终答案(由 generator 输出)
"""
import asyncio
import io
import re
import sys
from kag.interface import SolverPipelineABC
from kag.common.conf import KAG_CONFIG
from builder import prompt


class TeeStdout:
    def __init__(self, original):
        self.original = original
        self.buffer = io.StringIO()

    def write(self, s):
        self.original.write(s)
        self.buffer.write(s)

    def flush(self):
        self.original.flush()

    def getvalue(self):
        return self.buffer.getvalue()


async def qa_with_evidence(question):
    pipeline = SolverPipelineABC.from_config(
        KAG_CONFIG.all_config["kag_solver_pipeline"]
    )

    # 头部
    header = "\n" + "═" * 80 + f"\n❓ 问题: {question}\n" + "═" * 80
    print(header)

    # 抓 stdout
    tee = TeeStdout(sys.stdout)
    sys.stdout = tee
    try:
        final_answer = await pipeline.ainvoke(question)
    finally:
        sys.stdout = tee.original

    captured = tee.getvalue()

    # === 一、检索证据 ===
    print("\n" + "─" * 80)
    print("📑 一、检索证据")
    print("─" * 80)

    m = re.search(r"Tasks:\s*\n+(\[.*?\])\n+Final Answer:", captured, re.S)
    if not m:
        print("(未能解析检索过程)\n")
    else:
        sub_tasks = _split_sub_tasks(m.group(1))
        retriever_idx = 0
        for raw in sub_tasks:
            evidence = _extract_evidence(raw)
            if evidence is None:
                continue
            retriever_idx += 1
            print(f"\n【证据 {retriever_idx}】")
            print(f"  🔍 检索问题: {evidence['sub_q']}")
            if evidence['source']:
                print(f"  📂 来源定位: {evidence['source']}")
            print(f"  💡 检索结论:")
            for line in evidence['conclusion'].split("\n"):
                print(f"      {line.strip()}")

    # === 二、最终答案 ===
    print("\n" + "─" * 80)
    print("✅ 二、综合答案")
    print("─" * 80)
    print(final_answer.strip())
    print()
    return final_answer


def _split_sub_tasks(tasks_repr):
    """按顶层 '}, {' 切分子任务"""
    s = tasks_repr.strip().lstrip("[").rstrip("]")
    parts, depth, buf, i = [], 0, [], 0
    while i < len(s):
        ch = s[i]
        if ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth -= 1
        if (depth == 0 and ch == "}" and i + 3 < len(s)
                and s[i+1:i+3] == ", " and s[i+3] == "{"):
            buf.append(ch)
            parts.append("".join(buf))
            buf = []
            i += 3
            continue
        buf.append(ch)
        i += 1
    if buf:
        parts.append("".join(buf))
    return parts


def _extract_evidence(raw):
    """
    从单个子任务的 repr 文本里提取证据。
    只保留 Retriever 类型,跳过 Deduce / Output。
    返回 {sub_q, source, conclusion} 或 None。
    """
    m_lf = re.search(r"logic_form_node':\s*(\w+)\(", raw)
    if not m_lf or m_lf.group(1) != "Retriever":
        return None

    # 子问题
    m_q = re.search(r"'query':\s*'([^']*)'", raw)
    sub_q = m_q.group(1) if m_q else ""

    # 来源定位:LLM 思考链中通常会说"在文档第 X 节"、"报告 XXX 中"
    m_src = re.search(
        r"(?:在|从)?(?:文档|报告)[的]?\s*([^。\n]{4,40}?(?:节|章|部分|分析|描述|摘要))",
        raw,
    )
    source = m_src.group(1).strip() if m_src else ""

    # 结论:截取最后一个"结论:"或"结论："后的内容
    m_concl = re.findall(r"结论[::]\s*\n?\s*(.+?)(?=\]\s*,sub_query|init_query|$)", raw, re.S)
    if m_concl:
        conclusion = m_concl[-1].strip().rstrip(",").rstrip("'").rstrip('"').strip()
        # 清掉首尾的引号和反斜杠转义
        conclusion = conclusion.replace("\\n", "\n").strip("'\" \n")
    else:
        conclusion = "(未提取到明确结论)"

    return {
        "sub_q": sub_q,
        "source": source,
        "conclusion": conclusion,
    }


if __name__ == "__main__":
    questions = [
        "广州14/21号线高度阀卡滞问题风险是什么？报告中给了哪些后续措施",
        "故障5228的故障原因",
    ]
    for q in questions:
        asyncio.run(qa_with_evidence(q))
        print()
