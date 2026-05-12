# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0

import os
import sys
import logging

# 让 Python 能找到同目录下的 prompt 子包(必须在 import prompt 之前)
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

from kag.common.conf import KAG_CONFIG
from kag.builder.runner import BuilderChainRunner

# 触发 @PromptABC.register("kgtest_ner") / ("kgtest_triple") 注册
import prompt  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def buildKB(file_path):
    runner = BuilderChainRunner.from_config(
        KAG_CONFIG.all_config["kag_builder_pipeline"]
    )
    runner.invoke(file_path)
    logger.info(f"Build finished: {file_path}")


if __name__ == "__main__":

    data_dir = os.path.join(THIS_DIR, "data")
    file_path = os.path.join(data_dir, "8D_佛山3号线T15列车制动不缓解调查报告_清洗版.md")

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        logger.info(f"Files under {data_dir}:")
        if os.path.exists(data_dir):
            for f in os.listdir(data_dir):
                logger.info(f"  - {f}")
        raise SystemExit(1)

    buildKB(file_path)
