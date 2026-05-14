# -*- coding: utf-8 -*-
"""KGtestV2 简洁两段式答案生成器"""
from kag.interface import PromptABC


@PromptABC.register("kgtest_concise_generator")
class KGTestConciseGeneratorPrompt(PromptABC):
    template_zh = """你是一位轨道交通故障分析专家。请基于下面提供的检索内容，回答用户问题。

【检索内容】
$content

【用户问题】
$question

【回答要求】
1. 直接给出答案，不要复述问题，不要客套话。
2. 使用分点形式，每点不超过 50 字，要点清晰。
3. 禁止使用"进而""同时""此外""主要包括""具体表现为"等冗余连接词。
4. 如检索内容中无相关信息，直接回答"未在知识库中找到相关信息"，不要编造。
5. 如问题包含多个子问题，使用小标题分段回答。

【回答】"""

    template_en = template_zh

    @property
    def template_variables(self):
        return ["question", "content"]

    def parse_response(self, response, **kwargs):
        if isinstance(response, str):
            return response.strip()
        return str(response).strip()
