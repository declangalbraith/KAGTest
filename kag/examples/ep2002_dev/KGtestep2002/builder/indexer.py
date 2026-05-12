# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

import os
import logging
from kag.common.registry import import_modules_from_path
from kag.common.conf import KAG_CONFIG
from kag.builder.runner import BuilderChainRunner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# 让 Python 能找到同目录下的 prompt 子包
THIS_DIR = os.path.dirname(os.path.abspath(__file__))      # ...\KGtestep2002\builder
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

# 触发 @PromptABC.register("kgtest_ner") / ("kgtest_triple") 注册
import prompt  # noqa: F401   # 等价于 import builder/prompt/__init__.py

def buildKB(file_path):
    runner = BuilderChainRunner.from_config(
        KAG_CONFIG.all_config["kag_builder_pipeline"]
    )
    runner.invoke(file_path)
    logger.info(f"Build finished: {file_path}")


if __name__ == "__main__":
    import_modules_from_path(".")

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    # 抽取 data 目录下的指定文件
    file_path = os.path.join(data_dir, "8D_EP2002_OpenSPG_simple_extract.md")

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        logger.info(f"Files under {data_dir}:")
        if os.path.exists(data_dir):
            for f in os.listdir(data_dir):
                logger.info(f"  - {f}")
        raise SystemExit(1)

    buildKB(file_path)
