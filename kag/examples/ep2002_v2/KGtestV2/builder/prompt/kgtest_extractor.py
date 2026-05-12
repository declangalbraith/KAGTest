# -*- coding: utf-8 -*-
"""
KGtestV2：在 schema_constraint 流程中复用 NER(parse_response) 已拆出的五元组，
经 add_relations_to_graph 写入 SubGraph，再由 kg_writer 提交 OpenSPG。
避免二次 LLM；kag_config 中仍配置 relation_prompt 作为无缓存时的兜底。
"""
import logging

from kag.builder.component.extractor.schema_constraint_extractor import (
    SchemaConstraintExtractor,
)
from kag.interface import ExtractorABC

logger = logging.getLogger(__name__)


@ExtractorABC.register("kgtest_schema_constraint_extractor")
class KGTestSchemaConstraintExtractor(SchemaConstraintExtractor):
    def relations_extraction(self, passage: str, entities: list):
        ner = self.ner_prompt
        if getattr(ner, "_ner_relation_triples_ready", False):
            triples = getattr(ner, "_last_relation_triples", []) or []
            logger.debug(
                "relations_extraction: use %d triples from NER cache",
                len(triples),
            )
            return list(triples)
        return super().relations_extraction(passage, entities)

    async def arelations_extraction(self, passage: str, entities: list):
        ner = self.ner_prompt
        if getattr(ner, "_ner_relation_triples_ready", False):
            triples = getattr(ner, "_last_relation_triples", []) or []
            logger.debug(
                "arelations_extraction: use %d triples from NER cache",
                len(triples),
            )
            return list(triples)
        return await super().arelations_extraction(passage, entities)
