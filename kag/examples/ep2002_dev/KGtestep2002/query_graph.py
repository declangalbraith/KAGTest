from kag.common.conf import KAG_CONFIG, init_env
init_env()
from knext.reasoner.client import ReasonerClient

cfg = KAG_CONFIG.all_config["project"]
host = cfg["host_addr"]
proj_id = int(cfg.get("id", "3"))
ns = cfg["namespace"]

client = ReasonerClient(host_addr=host, project_id=proj_id)

types = ["EightDReport","FailureMode","BOMPart","CauseItem","ActionItem",
         "ProductEvent","Person","Organization","PartSerial",
         "ProductInstance","ProductModel","Installation"]

for t in types:
    dsl = f"MATCH (n:`{ns}.{t}`) RETURN count(n) AS cnt"
    try:
        res = client.syn_execute(dsl_content=dsl)
        print(f"{t}: {res}")
    except Exception as e:
        print(f"{t}: 失败 - {type(e).__name__}: {e}")
