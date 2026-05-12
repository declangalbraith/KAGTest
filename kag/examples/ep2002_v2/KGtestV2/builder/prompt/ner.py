# -*- coding: utf-8 -*-
"""
KGtestV2 项目自定义 NER prompt（关系内嵌在 properties 中）
继承 SPGEntityPrompt，自动从 SchemaClient 加载 schema。
关系通过实体 properties 中的关系字段直接产出，由 KG writer 写成命名边。
"""
from kag.interface import PromptABC
from kag.builder.prompt.spg_prompt import SPGEntityPrompt

ALLOWED_TYPES = [
    "ProductModel", "ProductInstance", "BOMPart", "PartSerial",
    "Installation", "ProductEvent", "EightDReport", "CauseItem",
    "ActionItem", "FailureMode", "EventCategory", "Organization",
]
ALLOWED_TYPES_STR = "、".join(ALLOWED_TYPES)

@PromptABC.register("kgtest_ner")
class KGTestNERPrompt(SPGEntityPrompt):
    template_zh = {
        "instruction": (
            "你是一名工业产品质量领域(8D报告)的图谱抽取专家。\n"
            "请严格按照 schema 中给出的实体类型和属性抽取实体。\n"
            "\n"
            "## 硬性要求\n"
            "1) category 只能是白名单中的类型: " + ALLOWED_TYPES_STR + "。\n"
            "2) 文本中不属于白名单的实体直接忽略。\n"
            "3) 严禁创建新类型，严禁出现 Person、Location 类型。\n"
            "4) 人员姓名作为属性写入对应实体（ownerName / reporterName / operatorName 等），不单独建实体。\n"
            "5) 地点信息作为属性写入 ProductInstance（siteCity / siteCountry / siteCode 等），不单独建实体。\n"
            "6) 列表型属性输出为 JSON 数组，缺失值用 null。\n"
            "7) 输出严格的 JSON 数组，不要解释、不要 markdown 代码块、不要思考过程。\n"
            "\n"
            "## 关系字段处理（重要）\n"
            "8) schema 中每个实体下的 relation 字段（如 EightDReport 的 rootCause、correctiveAction、"
            "affectedPart 等），必须以**字符串数组**形式填入 properties，每个字符串是另一个被抽取实体的 name。\n"
            "9) 关系字段值中的 name **必须**与本次输出列表中某个实体的 name **完全一致**（一字不差）。\n"
            "10) 如果某关系在文本中没有明确对应的实体，该字段填 null 或省略，不要编造。\n"
            "11) 关系字段的目标实体必须先在同一份 JSON 输出中作为独立实体抽取出来，再被引用。\n"
            "\n"
            "## 业务规则\n"
            "12) ProductModel 表示型号（如 EP2002阀）；ProductInstance 表示具体安装的某台设备。\n"
            "13) BOMPart 是设计件（部件类型/位号/层级）；PartSerial 是带序列号的物理件。\n"
            "14) 疲劳/压力超差/泄漏等失效现象统一抽为 FailureMode。\n"
            "15) CauseItem、ActionItem 必须在 properties 中填 evidence 字段（30~150字原文摘录）。\n"
            "16) ActionItem.actionType 使用带 D 编号的值，如 \"纠正措施D5\"、\"预防措施D7\"。\n"
            "17) 8D 报告整篇只抽**一个** EightDReport 实体，reportNo 取报告号。\n"
            "\n"
            "## schema\n$schema\n\n## input\n$input"
        ),
        "example": [
            {
                "input": (
                    "EP2002阀二级调节器压力超差故障8D分析报告(报告号: 600812585)\n"
                    "客户A(德国慕尼黑现场)反馈EP2002阀压力超差。制造商: ABB；供应商: 富士康。\n"
                    "事件由黄海霞于2024-08-01上报，发生在序列号SN-EP2002-001的设备上。\n"
                    "故障部件为二级调节器弹簧(BOM件号 BP-SPRING-02，位号 P2-S)，失效模式为弹簧疲劳。\n"
                    "D4根因: 弹簧材料疲劳寿命不足。\n"
                    "D5纠正措施: 更换为新型弹簧组件。D7预防措施: 增加上线前压力循环测试。\n"
                    "8D 负责人: 王怀亮(质量工程师, 调节器事业部)。"
                ),
                "output": [
                    {
                        "category": "EightDReport",
                        "properties": {
                            "name": "EP2002阀二级调节器压力超差故障8D分析报告",
                            "reportNo": "600812585",
                            "issueTitle": "EP2002阀二级调节器压力超差",
                            "ownerName": "王怀亮",
                            "ownerRole": "质量工程师",
                            "d4RootCauseSummary": "弹簧材料疲劳寿命不足",
                            "d5PermanentCorrectionSummary": "更换为新型弹簧组件",
                            "d7PreventionSummary": "增加上线前压力循环测试",
                            "rootCause": ["弹簧材料疲劳寿命不足"],
                            "correctiveAction": ["更换为新型弹簧组件"],
                            "preventiveAction": ["增加上线前压力循环测试"],
                            "affectedPart": ["二级调节器弹簧"],
                            "affectedProduct": ["客户A现场EP2002阀(SN-EP2002-001)"],
                            "sourceEvent": ["EP2002阀压力超差事件"],
                            "responsibleOrg": ["调节器事业部"]
                        }
                    },
                    {
                        "category": "ProductModel",
                        "properties": {
                            "name": "EP2002阀",
                            "modelCode": "EP2002",
                            "manufacturerName": "ABB",
                            "manufacturer": ["ABB"],
                            "hasBOMPart": ["二级调节器弹簧"]
                        }
                    },
                    {
                        "category": "ProductInstance",
                        "properties": {
                            "name": "客户A现场EP2002阀(SN-EP2002-001)",
                            "serialNumber": "SN-EP2002-001",
                            "ownerName": "客户A",
                            "siteCity": "慕尼黑",
                            "siteCountry": "德国",
                            "basedOnModel": ["EP2002阀"],
                            "ownedBy": ["客户A"],
                            "has8D": ["EP2002阀二级调节器压力超差故障8D分析报告"],
                            "hasEvent": ["EP2002阀压力超差事件"]
                        }
                    },
                    {
                        "category": "BOMPart",
                        "properties": {
                            "name": "二级调节器弹簧",
                            "partNo": "BP-SPRING-02",
                            "positionCode": "P2-S",
                            "partType": "弹簧",
                            "belongsToModel": ["EP2002阀"],
                            "hasFailureMode": ["弹簧疲劳"]
                        }
                    },
                    {
                        "category": "FailureMode",
                        "properties": {
                            "name": "弹簧疲劳",
                            "modeCode": "FM-SPRING-FATIGUE"
                        }
                    },
                    {
                        "category": "ProductEvent",
                        "properties": {
                            "name": "EP2002阀压力超差事件",
                            "eventTime": "2024-08-01",
                            "symptom": "二级调节器压力超差",
                            "eventType": "故障",
                            "reporterName": "黄海霞",
                            "happenedOn": ["客户A现场EP2002阀(SN-EP2002-001)"],
                            "relatedFailureMode": ["弹簧疲劳"],
                            "relatedPart": ["二级调节器弹簧"],
                            "has8DReport": ["EP2002阀二级调节器压力超差故障8D分析报告"]
                        }
                    },
                    {
                        "category": "CauseItem",
                        "properties": {
                            "name": "弹簧材料疲劳寿命不足",
                            "title": "弹簧材料疲劳寿命不足",
                            "causeType": "D4根因",
                            "isVerified": "true",
                            "evidence": "D4根因: 弹簧材料疲劳寿命不足。",
                            "belongsToReport": ["EP2002阀二级调节器压力超差故障8D分析报告"],
                            "relatedFailureMode": ["弹簧疲劳"],
                            "relatedPart": ["二级调节器弹簧"]
                        }
                    },
                    {
                        "category": "ActionItem",
                        "properties": {
                            "name": "更换为新型弹簧组件",
                            "title": "更换为新型弹簧组件",
                            "actionType": "纠正措施D5",
                            "status": "已完成",
                            "evidence": "D5纠正措施: 更换为新型弹簧组件。",
                            "belongsToReport": ["EP2002阀二级调节器压力超差故障8D分析报告"],
                            "verifiesCause": ["弹簧材料疲劳寿命不足"],
                            "targetPart": ["二级调节器弹簧"]
                        }
                    },
                    {
                        "category": "ActionItem",
                        "properties": {
                            "name": "增加上线前压力循环测试",
                            "title": "增加上线前压力循环测试",
                            "actionType": "预防措施D7",
                            "status": "计划中",
                            "evidence": "D7预防措施: 增加上线前压力循环测试。",
                            "belongsToReport": ["EP2002阀二级调节器压力超差故障8D分析报告"]
                        }
                    },
                    {
                        "category": "Organization",
                        "properties": {"name": "ABB", "orgType": "制造商"}
                    },
                    {
                        "category": "Organization",
                        "properties": {"name": "富士康", "orgType": "供应商"}
                    },
                    {
                        "category": "Organization",
                        "properties": {"name": "客户A", "orgType": "客户"}
                    },
                    {
                        "category": "Organization",
                        "properties": {"name": "调节器事业部", "orgType": "内部部门"}
                    }
                ]
            }
        ]
    }
    template_en = template_zh

# === 重写 parse_response：schema relation 字段拆成五元组，供 kgtest_schema_constraint_extractor 写入图 ===
import json as _json
import os as _os
import time as _time

_DEBUG_DIR = _os.path.join(_os.path.dirname(__file__), "_llm_dump")


def _kgtest_parse_response(self, response, **kwargs):
    self._ner_relation_triples_ready = False
    self._last_relation_triples = []
    rsp = response
    if isinstance(rsp, str):
        rsp = _json.loads(rsp)
    if isinstance(rsp, dict) and "output" in rsp:
        rsp = rsp["output"]

    try:
        _os.makedirs(_DEBUG_DIR, exist_ok=True)
        ts = _time.strftime("%H%M%S") + f"_{int(_time.time()*1000)%1000:03d}"
        with open(_os.path.join(_DEBUG_DIR, f"ner_{ts}_raw.txt"), "w", encoding="utf-8") as f:
            f.write(_json.dumps(rsp, ensure_ascii=False, indent=2))
    except Exception:
        ts = "0"

    name_to_category = {}
    for item in rsp:
        if "category" not in item or item["category"] not in self.schema:
            continue
        props = item.get("properties", {})
        nm = props.get("name")
        if nm:
            name_to_category[nm] = item["category"]

    entity_outputs = []
    relation_triples = []

    for item in rsp:
        if "category" not in item or item["category"] not in self.schema:
            continue
        category = item["category"]
        properties = item.get("properties", {})
        if "name" not in properties:
            continue
        s_name = properties.pop("name")

        spg_type = self.schema.get(category)
        relation_map = {}
        if spg_type and getattr(spg_type, "relations", None):
            for k, v in spg_type.relations.items():
                rel_name = getattr(v, "name", None) if not isinstance(v, dict) else v.get("name")
                if not rel_name:
                    rel_name = k.split("_", 1)[0]
                relation_map[rel_name] = v

        clean_props = {}
        for k, v in properties.items():
            k_clean = self.process_property_name(k)
            if k_clean in relation_map:
                if v is None:
                    continue
                if not isinstance(v, list):
                    v = [v]
                rel_def = relation_map[k_clean]
                obj_type_full = (
                    getattr(rel_def, "object_type_name", None)
                    if not isinstance(rel_def, dict)
                    else rel_def.get("object_type_name")
                )
                o_label_default = (obj_type_full or "").split(".")[-1]
                for o_name in v:
                    if o_name is None or str(o_name).strip() == "":
                        continue
                    o_name_str = str(o_name).strip()
                    actual_o_label = name_to_category.get(o_name_str, o_label_default)
                    relation_triples.append(
                        [s_name, category, k_clean, o_name_str, actual_o_label]
                    )
            else:
                if isinstance(v, dict):
                    clean_props[k_clean] = self.process_property_names(v)
                else:
                    clean_props[k_clean] = v

        entity_outputs.append(
            {"category": category, "name": s_name, "properties": clean_props}
        )

    try:
        with open(_os.path.join(_DEBUG_DIR, f"ner_{ts}_entities.json"), "w", encoding="utf-8") as f:
            _json.dump(entity_outputs, f, ensure_ascii=False, indent=2)
        with open(_os.path.join(_DEBUG_DIR, f"ner_{ts}_relations.json"), "w", encoding="utf-8") as f:
            _json.dump(relation_triples, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    self._last_relation_triples = relation_triples
    self._ner_relation_triples_ready = True
    # 只返回实体，保证 _named_entity_recognition_process 不报错
    return entity_outputs


KGTestNERPrompt.parse_response = _kgtest_parse_response
