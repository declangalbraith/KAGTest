from kag.common.conf import KAG_CONFIG
import json
cfg = KAG_CONFIG.all_config["kag_builder_pipeline"]
print(json.dumps(cfg, indent=2, ensure_ascii=False))