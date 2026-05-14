# -*- coding: utf-8 -*-
"""
KGtestV2 项目自定义 NER prompt（关系内嵌在 properties 中）
继承 SPGEntityPrompt,自动从 SchemaClient 加载 schema。
关系通过实体 properties 中的关系字段直接产出,由 KG writer 写成命名边。

核心设计:
  - 让 name = 业务主键值,使 OpenSPG post_processor 和 cleanup 脚本都能
    按 name 对齐合并,实现"同业务主键 = 同一实体"的去重语义。
  - parse 阶段强制改写 name 为主键值,不依赖 LLM 完美遵守 prompt。
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
            "3) 严禁创建新类型,严禁出现 Person、Location 类型。\n"
            "4) 人员姓名作为属性写入对应实体(ownerName / reporterName / operatorName 等),不单独建实体。\n"
            "5) 地点信息作为属性写入 ProductInstance(siteCity / siteCountry / siteCode 等),不单独建实体。\n"
            "6) 列表型属性输出为 JSON 数组,缺失值用 null。\n"
            "7) 输出严格的 JSON 数组,不要解释、不要 markdown 代码块、不要思考过程。\n"
            "\n"
            "## 缺失值与占位符(极其重要)\n"
            "8) 当文本中没有给出某字段的明确值时,**必须**返回 null 或省略该字段。\n"
            "9) **严禁**编造任何占位符值,包括但不限于:\n"
            "   \"不明确\"、\"未知\"、\"未提供\"、\"未指定\"、\"暂无\"、\"无\"、\n"
            "   \"N/A\"、\"NA\"、\"None\"、\"null\",以及形如 \"SN-不明确\"、\n"
            "   \"未知序列号\" 等任何含上述词的拼接字符串。\n"
            "10) 字段值中**不要**包含多余的引号、转义字符。\n"
            "    错误示例: \"serialNumber\": \"\\\"2208059LZP\\\"\"\n"
            "    正确示例: \"serialNumber\": \"2208059LZP\"\n"
            "11) 如果文本只给出部分信息(如只有序列号但没有批次号),就只填序列号,其余字段返回 null。\n"
            "\n"
            "## name 字段规则(极其重要,直接影响实体合并)\n"
            "    name 字段是实体的合并键,必须严格遵守以下规则:\n"
            "21) EightDReport 的 name 必须严格等于 reportNo,例如:\n"
            "    reportNo=\"600812585\" -> name=\"600812585\"。\n"
            "    长标题放在 issueTitle 字段。\n"
            "22) ProductInstance 的 name 必须严格等于 serialNumber。\n"
            "    例如 serialNumber=\"2120124FOE\" -> name=\"2120124FOE\"。\n"
            "23) ProductModel 的 name 必须严格等于 modelCode。\n"
            "    例如 modelCode=\"EP2002\" -> name=\"EP2002\"。\n"
            "24) FailureMode 的 name 必须严格等于 modeCode。\n"
            "25) Installation 的 name 必须严格等于 installationId。\n"
            "26) BOMPart 的 name 必须严格等于 partNo。\n"
            "27) 对于 Organization / ProductEvent / CauseItem / ActionItem / PartSerial /\n"
            "    EventCategory 这些没有上面列出的明确业务主键的类型,\n"
            "    name 字段填该实体的**简短业务名称**(15字以内,稳定可复现),\n"
            "    例如 Organization.name=\"ABB\",CauseItem.name=\"弹簧材料疲劳寿命不足\"。\n"
            "    **禁止**把长描述、整段文字当作 name。\n"
            "\n"
            "## 关系字段处理\n"
            "28) schema 中每个实体下的 relation 字段(如 EightDReport 的 rootCause、correctiveAction、"
            "affectedPart 等),必须以**字符串数组**形式填入 properties,每个字符串是另一个被抽取实体的 name。\n"
            "29) 由于 21-27 规则,关系字段中引用的 name 也必须是对方实体的 name(即对方的主键值或短名),\n"
            "    例如引用一个 ProductInstance 时,要写它的 serialNumber 值,不要写\"客户A现场EP2002阀\"这样的长名。\n"
            "30) 关系字段值中的 name **必须**与本次输出列表中某个实体的 name **完全一致**(一字不差)。\n"
            "31) 如果某关系在文本中没有明确对应的实体,该字段填 null 或省略,不要编造。\n"
            "32) 关系字段的目标实体必须先在同一份 JSON 输出中作为独立实体抽取出来,再被引用。\n"
            "\n"
            "## 业务规则\n"
            "33) ProductModel 表示型号(如 EP2002阀);ProductInstance 表示具体安装的某台设备。\n"
            "34) BOMPart 是设计件(部件类型/位号/层级);PartSerial 是带序列号的物理件。\n"
            "35) 疲劳/压力超差/泄漏等失效现象统一抽为 FailureMode。\n"
            "36) CauseItem、ActionItem 必须在 properties 中填 evidence 字段(30~150字原文摘录)。\n"
            "37) ActionItem.actionType 使用带 D 编号的值,如 \"纠正措施D5\"、\"预防措施D7\"。\n"
            "38) 8D 报告整篇只抽**一个** EightDReport 实体,reportNo 取报告号。\n"
            "39) 若文档中根本未提及序列号,则**不要**输出 PartSerial / ProductInstance 实体,"
            "也不要用占位符替代——宁可漏抽,不可造假。\n"
            "\n"
            "## schema\n$schema\n\n## input\n$input"
        ),
        "example": [
            {
                "input": (
                    "EP2002阀二级调节器压力超差故障8D分析报告(报告号: 600812585)\n"
                    "客户A(德国慕尼黑现场)反馈EP2002阀压力超差。制造商: ABB;供应商: 富士康。\n"
                    "事件由黄海霞于2024-08-01上报,发生在序列号SN-EP2002-001的设备上。\n"
                    "故障部件为二级调节器弹簧(BOM件号 BP-SPRING-02,位号 P2-S),失效模式为弹簧疲劳。\n"
                    "D4根因: 弹簧材料疲劳寿命不足。\n"
                    "D5纠正措施: 更换为新型弹簧组件。D7预防措施: 增加上线前压力循环测试。\n"
                    "8D 负责人: 王怀亮(质量工程师, 调节器事业部)。"
                ),
                "output": [
                    {
                        "category": "EightDReport",
                        "properties": {
                            "name": "600812585",
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
                            "affectedPart": ["BP-SPRING-02"],
                            "affectedProduct": ["SN-EP2002-001"],
                            "sourceEvent": ["EP2002阀压力超差事件"],
                            "responsibleOrg": ["调节器事业部"]
                        }
                    },
                    {
                        "category": "ProductModel",
                        "properties": {
                            "name": "EP2002",
                            "modelCode": "EP2002",
                            "manufacturerName": "ABB",
                            "manufacturer": ["ABB"],
                            "hasBOMPart": ["BP-SPRING-02"]
                        }
                    },
                    {
                        "category": "ProductInstance",
                        "properties": {
                            "name": "SN-EP2002-001",
                            "serialNumber": "SN-EP2002-001",
                            "ownerName": "客户A",
                            "siteCity": "慕尼黑",
                            "siteCountry": "德国",
                            "basedOnModel": ["EP2002"],
                            "ownedBy": ["客户A"],
                            "has8D": ["600812585"],
                            "hasEvent": ["EP2002阀压力超差事件"]
                        }
                    },
                    {
                        "category": "BOMPart",
                        "properties": {
                            "name": "BP-SPRING-02",
                            "partNo": "BP-SPRING-02",
                            "positionCode": "P2-S",
                            "partType": "弹簧",
                            "belongsToModel": ["EP2002"],
                            "hasFailureMode": ["FM-SPRING-FATIGUE"]
                        }
                    },
                    {
                        "category": "FailureMode",
                        "properties": {
                            "name": "FM-SPRING-FATIGUE",
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
                            "happenedOn": ["SN-EP2002-001"],
                            "relatedFailureMode": ["FM-SPRING-FATIGUE"],
                            "relatedPart": ["BP-SPRING-02"],
                            "has8DReport": ["600812585"]
                        }
                    },
                    {
                        "category": "CauseItem",
                        "properties": {
                            "name": "弹簧材料疲劳寿命不足",
                            "title": "弹簧材料疲劳寿命不足",
                            "causeType": "根本原因",
                            "isVerified": "true",
                            "evidence": "D4根因: 弹簧材料疲劳寿命不足。",
                            "belongsToReport": ["600812585"],
                            "relatedFailureMode": ["FM-SPRING-FATIGUE"],
                            "relatedPart": ["BP-SPRING-02"]
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
                            "belongsToReport": ["600812585"],
                            "verifiesCause": ["弹簧材料疲劳寿命不足"],
                            "targetPart": ["BP-SPRING-02"]
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
                            "belongsToReport": ["600812585"]
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

# === 重写 parse_response:schema relation 字段拆成五元组,供 kgtest_schema_constraint_extractor 写入图 ===
import json as _json
import os as _os
import time as _time

_DEBUG_DIR = _os.path.join(_os.path.dirname(__file__), "_llm_dump")


# ---------- 值清洗工具 ----------
_PLACEHOLDER_TOKENS = (
    "不明确", "未知", "未提供", "未指定", "未说明", "暂无",
    "N/A", "n/a", "NA", "None", "none", "null", "NULL",
)
# 主键/标识类字段:占位符直接置 None,占位符 -> 整体实体丢弃
_KEY_LIKE_FIELDS = {
    "modelCode", "serialNumber", "partNo", "installationId",
    "eventId", "reportNo", "causeId", "actionId", "modeCode",
    "categoryCode", "orgCode", "batchNo",
}
# (category) -> (用作 name 的主键属性字段)
# 这些 category 的 name 强制改写为该属性的值,实现"同主键=同实体"的合并语义
_BUSINESS_KEY_OF_NAME = {
    "EightDReport":    "reportNo",
    "ProductInstance": "serialNumber",
    "ProductModel":    "modelCode",
    "FailureMode":     "modeCode",
    "Installation":    "installationId",
    "BOMPart":         "partNo",
    # 未列出的(Organization/ProductEvent/CauseItem/ActionItem/PartSerial/
    # EventCategory)继续用 LLM 给的短名作为 name,不做改写
}


def _strip_outer_quotes(s):
    """反复剥掉值外层成对的英文/中文双引号"""
    if not isinstance(s, str):
        return s
    prev = None
    cur = s.strip()
    while prev != cur:
        prev = cur
        if len(cur) >= 2:
            if (cur[0] == '"' and cur[-1] == '"') or \
               (cur[0] == "'" and cur[-1] == "'") or \
               (cur[0] == "“" and cur[-1] == "”") or \
               (cur[0] == "‘" and cur[-1] == "’"):
                cur = cur[1:-1].strip()
    return cur


def _is_placeholder(s, strict):
    if s is None or s == "":
        return True
    if strict:
        return any(tok in s for tok in _PLACEHOLDER_TOKENS)
    return s.strip() in _PLACEHOLDER_TOKENS


def _clean_scalar(v, field_name):
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = _strip_outer_quotes(v)
        strict = field_name in _KEY_LIKE_FIELDS
        if _is_placeholder(s, strict):
            return None
        return s
    return v


def _clean_value(v, field_name):
    if isinstance(v, list):
        cleaned = []
        for item in v:
            c = _clean_value(item, field_name)
            if c is not None and c != "":
                cleaned.append(c)
        return cleaned if cleaned else None
    if isinstance(v, dict):
        return {k: _clean_value(val, k) for k, val in v.items()}
    return _clean_scalar(v, field_name)


def _kgtest_parse_response(self, response, **kwargs):
    self._ner_relation_triples_ready = False
    self._last_relation_triples = []
    rsp = response

    # 反复 json.loads,防御双重序列化
    for _ in range(3):
        if isinstance(rsp, str):
            try:
                rsp = _json.loads(rsp)
            except Exception:
                break
        else:
            break
    if isinstance(rsp, dict) and "output" in rsp:
        rsp = rsp["output"]
    if not isinstance(rsp, list):
        rsp = []

    try:
        _os.makedirs(_DEBUG_DIR, exist_ok=True)
        ts = _time.strftime("%H%M%S") + f"_{int(_time.time()*1000)%1000:03d}"
        with open(_os.path.join(_DEBUG_DIR, f"ner_{ts}_raw.txt"), "w", encoding="utf-8") as f:
            f.write(_json.dumps(rsp, ensure_ascii=False, indent=2))
    except Exception:
        ts = "0"

    # ============ 第一遍:预处理,把 name 改写为业务主键值 ============
    # 同时建立 "LLM 原始 name -> 改写后 name" 的映射,用于后续关系端点改写。
    name_remap = {}  # 原 name -> 改写后 name
    for item in rsp:
        if not isinstance(item, dict):
            continue
        if "category" not in item or item["category"] not in self.schema:
            continue
        category = item["category"]
        properties = item.get("properties", {}) or {}
        orig_name = properties.get("name")
        if isinstance(orig_name, str):
            orig_name_clean = _strip_outer_quotes(orig_name).strip()
        else:
            orig_name_clean = orig_name

        # 检查是否需要改写 name
        key_field = _BUSINESS_KEY_OF_NAME.get(category)
        if key_field:
            pk_val = properties.get(key_field)
            if isinstance(pk_val, str):
                pk_val_clean = _clean_scalar(pk_val, key_field)
            else:
                pk_val_clean = pk_val
            if pk_val_clean and isinstance(pk_val_clean, str) and pk_val_clean.strip():
                new_name = pk_val_clean.strip()
                # 同步更新 properties["name"]
                properties["name"] = new_name
                if orig_name_clean and orig_name_clean != new_name:
                    name_remap[orig_name_clean] = new_name
                # 也允许带引号的原 name 被映射
                if isinstance(orig_name, str) and orig_name != new_name:
                    name_remap[orig_name] = new_name
            # 若主键缺失,name 保持 LLM 给的值,后续若 name 也是占位符会被丢弃

    # ============ 第二遍:构建 name -> category 映射 ============
    name_to_category = {}
    for item in rsp:
        if not isinstance(item, dict):
            continue
        if "category" not in item or item["category"] not in self.schema:
            continue
        props = item.get("properties", {}) or {}
        nm = props.get("name")
        if isinstance(nm, str):
            nm = _strip_outer_quotes(nm).strip()
        if nm:
            name_to_category[nm] = item["category"]

    # ============ 第三遍:正式解析为实体 + 五元组 ============
    entity_outputs = []
    relation_triples = []
    dropped_count = {
        "placeholder_key": 0, "empty_name": 0, "no_name": 0, "no_category": 0,
    }

    for item in rsp:
        if not isinstance(item, dict):
            dropped_count["no_category"] += 1
            continue
        if "category" not in item or item["category"] not in self.schema:
            dropped_count["no_category"] += 1
            continue
        category = item["category"]
        properties = item.get("properties", {}) or {}
        if "name" not in properties:
            dropped_count["no_name"] += 1
            continue

        # 清洗 name
        s_name_raw = properties.pop("name")
        s_name = _clean_scalar(s_name_raw, "name") if isinstance(s_name_raw, str) \
                 else s_name_raw
        if not s_name or not isinstance(s_name, str) or s_name.strip() == "":
            dropped_count["empty_name"] += 1
            continue
        s_name = s_name.strip()

        spg_type = self.schema.get(category)
        relation_map = {}
        if spg_type and getattr(spg_type, "relations", None):
            for k, v in spg_type.relations.items():
                rel_name = getattr(v, "name", None) if not isinstance(v, dict) else v.get("name")
                if not rel_name:
                    rel_name = k.split("_", 1)[0]
                relation_map[rel_name] = v

        clean_props = {}
        drop_entity = False

        for k, v in properties.items():
            k_clean = self.process_property_name(k)

            if k_clean in relation_map:
                # 关系字段
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
                    if o_name is None:
                        continue
                    o_clean = _clean_scalar(o_name, "name") if isinstance(o_name, str) else o_name
                    if o_clean is None or str(o_clean).strip() == "":
                        continue
                    o_name_str = str(o_clean).strip()
                    # 如果 LLM 在关系端点用了"原始长名",改写为主键值 name
                    if o_name_str in name_remap:
                        o_name_str = name_remap[o_name_str]
                    actual_o_label = name_to_category.get(o_name_str, o_label_default)
                    relation_triples.append(
                        [s_name, category, k_clean, o_name_str, actual_o_label]
                    )
            else:
                # 普通属性
                cleaned_v = _clean_value(v, k_clean)
                # 主键字段被清洗成 None -> 整个实体丢弃
                if k_clean in _KEY_LIKE_FIELDS and cleaned_v is None and v is not None:
                    dropped_count["placeholder_key"] += 1
                    drop_entity = True
                    break
                if cleaned_v is None or cleaned_v == "" or cleaned_v == []:
                    continue
                clean_props[k_clean] = cleaned_v

        if drop_entity:
            continue

        entity_outputs.append(
            {"category": category, "name": s_name, "properties": clean_props}
        )

    try:
        with open(_os.path.join(_DEBUG_DIR, f"ner_{ts}_entities.json"), "w", encoding="utf-8") as f:
            _json.dump(entity_outputs, f, ensure_ascii=False, indent=2)
        with open(_os.path.join(_DEBUG_DIR, f"ner_{ts}_relations.json"), "w", encoding="utf-8") as f:
            _json.dump(relation_triples, f, ensure_ascii=False, indent=2)
        with open(_os.path.join(_DEBUG_DIR, f"ner_{ts}_stats.json"), "w", encoding="utf-8") as f:
            _json.dump({
                "entities_kept": len(entity_outputs),
                "relations_kept": len(relation_triples),
                "dropped": dropped_count,
                "name_remapped": len(name_remap),
            }, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    self._last_relation_triples = relation_triples
    self._ner_relation_triples_ready = True
    return entity_outputs


KGTestNERPrompt.parse_response = _kgtest_parse_response
