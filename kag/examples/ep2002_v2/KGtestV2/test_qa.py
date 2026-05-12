# test_qa.py
import asyncio
from kag.common.conf import KAG_CONFIG
from kag.interface import SolverPipelineABC

async def run_query(question: str):
    print(f"\n{'='*60}\n问题: {question}\n{'='*60}")
    pipeline_conf = KAG_CONFIG.all_config["kag_solver_pipeline"]
    pipeline = SolverPipelineABC.from_config(pipeline_conf)
    answer = await pipeline.ainvoke(question)
    print(f"\n答案:\n{answer}\n")
    return answer

if __name__ == "__main__":
    questions = [
        "关于复兴号动车组供风单元干燥器故障是如何解决的",
        "复兴号动车供风单元干燥器故障5228 的故障原因是什么",
        "活塞销气孔的根本原因是什么",
    ]
    for q in questions:
        asyncio.run(run_query(q))
