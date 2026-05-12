# -*- coding: utf-8 -*-
"""
KGtestV2 项目自定义关系抽取 prompt。
继承 KAG 内置 OpenIETriplePrompt(default_triple),沿用其简单的
[subject, predicate, object] 三元数组输出格式,
只重写 instruction 与 example,加入"白名单关系名"硬约束。
"""

from kag.builder.prompt.default.triple import OpenIETriplePrompt
from kag.interface import PromptABC


# 白名单:与 schema/KGtestV2.schema 中所有 EntityType 的 relations 完全对齐。
# 同时把 NER 阶段已经下沉为属性的"人员/地点关系"排除在外。
ALLOWED_RELATIONS = [
    # ProductModel
    ("ProductModel",   "manufacturer",        "Organization",    "制造商"),
    ("ProductModel",   "hasBOMPart",          "BOMPart",         "包含BOM件"),
    ("ProductModel",   "hasBOMRoot",          "BOMPart",         "根BOM"),
    ("ProductModel",   "hasInstance",         "ProductInstance", "产品实例"),
    # ProductInstance
    ("ProductInstance","basedOnModel",        "ProductModel",    "对应型号"),
    ("ProductInstance","has8D",               "EightDReport",    "关联8D"),
    ("ProductInstance","hasInstallation",     "Installation",    "安装记录"),
    ("ProductInstance","hasCurrentPart",      "PartSerial",      "当前安装件"),
    ("ProductInstance","hasEvent",            "ProductEvent",    "发生事件"),
    ("ProductInstance","ownedBy",             "Organization",    "所属客户"),
    # BOMPart
    ("BOMPart",        "parentPart",          "BOMPart",         "上级BOM件"),
    ("BOMPart",        "fulfilledBy",         "PartSerial",      "对应实例件"),
    ("BOMPart",        "childPart",           "BOMPart",         "下级BOM件"),
    ("BOMPart",        "hasFailureMode",      "FailureMode",     "失效模式"),
    ("BOMPart",        "belongsToModel",      "ProductModel",    "所属型号"),
    ("BOMPart",        "alternativePart",     "BOMPart",         "替代件"),
    # PartSerial
    ("PartSerial",     "involvedIn8D",        "EightDReport",    "关联8D"),
    ("PartSerial",     "involvedInEvent",     "ProductEvent",    "关联事件"),
    ("PartSerial",     "replacedBy",          "PartSerial",      "替换后件"),
    ("PartSerial",     "replaces",            "PartSerial",      "替换前件"),
    ("PartSerial",     "instanceOfPart",      "BOMPart",         "对应设计件"),
    ("PartSerial",     "suppliedBy",          "Organization",    "供应商"),
    ("PartSerial",     "installedOn",         "ProductInstance", "安装于产品"),
    # Installation
    ("Installation",   "product",             "ProductInstance", "产品实例"),
    ("Installation",   "partSerial",          "PartSerial",      "实际安装件"),
    ("Installation",   "bomPart",             "BOMPart",         "对应BOM件"),
    ("Installation",   "generatedByEvent",    "ProductEvent",    "来源事件"),
    # ProductEvent
    ("ProductEvent",   "happenedOn",          "ProductInstance", "发生于产品"),
    ("ProductEvent",   "responsibleOrg",      "Organization",    "责任组织"),
    ("ProductEvent",   "relatedFailureMode",  "FailureMode",     "关联失效模式"),
    ("ProductEvent",   "category",            "EventCategory",   "事件分类"),
    ("ProductEvent",   "relatedInstallation", "Installation",    "关联安装记录"),
    ("ProductEvent",   "relatedSerial",       "PartSerial",      "关联序列件"),
    ("ProductEvent",   "relatedPart",         "BOMPart",         "关联设计件"),
    ("ProductEvent",   "has8DReport",         "EightDReport",    "8D报告"),
    # EightDReport
    ("EightDReport",   "sourceEvent",         "ProductEvent",    "源事件"),
    ("EightDReport",   "affectedProduct",     "ProductInstance", "影响产品"),
    ("EightDReport",   "affectedSerial",      "PartSerial",      "影响序列件"),
    ("EightDReport",   "affectedPart",        "BOMPart",         "影响设计件"),
    ("EightDReport",   "rootCause",           "CauseItem",       "根因项"),
    ("EightDReport",   "correctiveAction",    "ActionItem",      "纠正措施"),
    ("EightDReport",   "preventiveAction",    "ActionItem",      "预防措施"),
    ("EightDReport",   "responsibleOrg",      "Organization",    "责任组织"),
    # CauseItem
    ("CauseItem",      "relatedFailureMode",  "FailureMode",     "关联失效模式"),
    ("CauseItem",      "relatedPart",         "BOMPart",         "关联设计件"),
    ("CauseItem",      "relatedSerial",       "PartSerial",      "关联序列件"),
    ("CauseItem",      "belongsToReport",     "EightDReport",    "所属8D"),
    ("CauseItem",      "relatedEvent",        "ProductEvent",    "关联事件"),
    # ActionItem
    ("ActionItem",     "belongsToReport",     "EightDReport",    "所属8D"),
    ("ActionItem",     "verifiesCause",       "CauseItem",       "验证原因项"),
    ("ActionItem",     "relatedEvent",        "ProductEvent",    "关联事件"),
    ("ActionItem",     "targetSerial",        "PartSerial",      "作用序列件"),
    ("ActionItem",     "targetProduct",       "ProductInstance", "作用产品"),
    ("ActionItem",     "targetPart",          "BOMPart",         "作用设计件"),
    ("ActionItem",     "responsibleOrg",      "Organization",    "责任组织"),
    # EventCategory
    ("EventCategory",  "parentCategory",      "EventCategory",   "上级分类"),
]

# 仅取谓词英文名做白名单(KAG 的 default_triple 解析器不关心头/尾类型)
PREDICATE_WHITELIST = sorted({p for _, p, _, _ in ALLOWED_RELATIONS})
PREDICATE_WHITELIST_STR = ", ".join(PREDICATE_WHITELIST)

# 同时给 LLM 一个"头类型 -[谓词]-> 尾类型"的可读速查表
RELATION_LINES = "\n".join(
    f"  - ({h}) -[{p} / {zh}]-> ({t})"
    for h, p, t, zh in ALLOWED_RELATIONS
)


@PromptABC.register("kgtest_triple")
class KGTestTriplePrompt(OpenIETriplePrompt):
    """
    继承 default_triple,沿用 [s, p, o] 数组格式,只覆盖 instruction 和 example。
    KAG 在 schema_constraint_extractor 里会用实体名回查 NER 实体表得到类型,
    所以输出里不需要(也不要)写 subject_type / object_type。
    """

    template_zh = (
        "{\n"
        "  \"instruction\": \""
        "你是一名工业产品质量领域(8D 报告)的关系抽取专家。"
        "请基于 input 文本和 entity_list 中给出的实体,抽取实体之间的关系,"
        "输出 JSON 格式 {\\\"triples\\\": [[\\\"主语\\\", \\\"谓词\\\", \\\"宾语\\\"]]}。"
        "硬性要求:"
        "1) 谓词只能从下面的关系白名单中取(英文名),严禁创造新关系名,"
        "严禁使用 涉及/相关/关联到/source/officialName 等通用词;"
        "2) 主语和宾语必须严格使用 entity_list 中已抽出的实体 name(完全一致);"
        "3) 头/尾实体类型必须匹配关系白名单中的类型组合,"
        "若两个实体类型不匹配该关系,跳过不输出;"
        "4) 不要生成涉及 Person 或 Location 的关系——这些信息已在 NER 阶段写入实体属性;"
        "5) 因果链:CauseItem 之间不直接连边,通过共同的 EightDReport(belongsToReport) 和 "
        "ProductEvent(relatedEvent) 关联,causeType 字段在 NER 阶段已写入;"
        "6) 输出严格 JSON,不要解释、不要 markdown、不要思考过程。"
        "\\n关系白名单(谓词):" + PREDICATE_WHITELIST_STR + ""
        "\\n类型组合参考(头类型 -[谓词 / 中文]-> 尾类型):\\n" + RELATION_LINES.replace("\n", "\\n") + "\","
        "\n"
        "  \"entity_list\": $entity_list,\n"
        "  \"input\": \"$input\",\n"
        "  \"example\": {\n"
        "    \"input\": \"EP2002阀二级调节器压力超差故障8D分析报告(8D-2022-0814)。"
        "EP2002阀的制造商是ABB,塑料活塞销由富士康供货。"
        "事件发生在客户A现场EP2002阀上,失效模式是压力超差。"
        "根本原因是塑料活塞销存在气孔导致其强度变弱。"
        "永久纠正措施是更换为金属活塞销;预防措施是BOM上活塞销材料由塑料改为金属。\",\n"
        "    \"entity_list\": [\n"
        "      {\"name\": \"EP2002阀二级调节器压力超差故障8D分析报告\", \"category\": \"EightDReport\"},\n"
        "      {\"name\": \"EP2002阀\", \"category\": \"ProductModel\"},\n"
        "      {\"name\": \"客户A现场EP2002阀\", \"category\": \"ProductInstance\"},\n"
        "      {\"name\": \"二级调节器\", \"category\": \"BOMPart\"},\n"
        "      {\"name\": \"塑料活塞销\", \"category\": \"BOMPart\"},\n"
        "      {\"name\": \"压力超差\", \"category\": \"FailureMode\"},\n"
        "      {\"name\": \"EP2002阀二级调节器压力超差事件\", \"category\": \"ProductEvent\"},\n"
        "      {\"name\": \"塑料活塞销存在气孔导致其强度变弱\", \"category\": \"CauseItem\"},\n"
        "      {\"name\": \"更换为金属活塞销\", \"category\": \"ActionItem\"},\n"
        "      {\"name\": \"BOM上活塞销材料由塑料改为金属\", \"category\": \"ActionItem\"},\n"
        "      {\"name\": \"ABB\", \"category\": \"Organization\"},\n"
        "      {\"name\": \"客户A\", \"category\": \"Organization\"},\n"
        "      {\"name\": \"富士康\", \"category\": \"Organization\"}\n"
        "    ],\n"
        "    \"output\": [\n"
        "      [\"EP2002阀\", \"manufacturer\", \"ABB\"],\n"
        "      [\"EP2002阀\", \"hasBOMPart\", \"二级调节器\"],\n"
        "      [\"EP2002阀\", \"hasInstance\", \"客户A现场EP2002阀\"],\n"
        "      [\"客户A现场EP2002阀\", \"basedOnModel\", \"EP2002阀\"],\n"
        "      [\"客户A现场EP2002阀\", \"ownedBy\", \"客户A\"],\n"
        "      [\"客户A现场EP2002阀\", \"hasEvent\", \"EP2002阀二级调节器压力超差事件\"],\n"
        "      [\"客户A现场EP2002阀\", \"has8D\", \"EP2002阀二级调节器压力超差故障8D分析报告\"],\n"
        "      [\"二级调节器\", \"belongsToModel\", \"EP2002阀\"],\n"
        "      [\"塑料活塞销\", \"belongsToModel\", \"EP2002阀\"],\n"
        "      [\"塑料活塞销\", \"parentPart\", \"二级调节器\"],\n"
        "      [\"塑料活塞销\", \"hasFailureMode\", \"压力超差\"],\n"
        "      [\"EP2002阀二级调节器压力超差事件\", \"happenedOn\", \"客户A现场EP2002阀\"],\n"
        "      [\"EP2002阀二级调节器压力超差事件\", \"relatedFailureMode\", \"压力超差\"],\n"
        "      [\"EP2002阀二级调节器压力超差事件\", \"relatedPart\", \"塑料活塞销\"],\n"
        "      [\"EP2002阀二级调节器压力超差事件\", \"has8DReport\", \"EP2002阀二级调节器压力超差故障8D分析报告\"],\n"
        "      [\"EP2002阀二级调节器压力超差故障8D分析报告\", \"sourceEvent\", \"EP2002阀二级调节器压力超差事件\"],\n"
        "      [\"EP2002阀二级调节器压力超差故障8D分析报告\", \"affectedProduct\", \"客户A现场EP2002阀\"],\n"
        "      [\"EP2002阀二级调节器压力超差故障8D分析报告\", \"affectedPart\", \"塑料活塞销\"],\n"
        "      [\"EP2002阀二级调节器压力超差故障8D分析报告\", \"rootCause\", \"塑料活塞销存在气孔导致其强度变弱\"],\n"
        "      [\"EP2002阀二级调节器压力超差故障8D分析报告\", \"correctiveAction\", \"更换为金属活塞销\"],\n"
        "      [\"EP2002阀二级调节器压力超差故障8D分析报告\", \"preventiveAction\", \"BOM上活塞销材料由塑料改为金属\"],\n"
        "      [\"塑料活塞销存在气孔导致其强度变弱\", \"belongsToReport\", \"EP2002阀二级调节器压力超差故障8D分析报告\"],\n"
        "      [\"塑料活塞销存在气孔导致其强度变弱\", \"relatedEvent\", \"EP2002阀二级调节器压力超差事件\"],\n"
        "      [\"塑料活塞销存在气孔导致其强度变弱\", \"relatedFailureMode\", \"压力超差\"],\n"
        "      [\"塑料活塞销存在气孔导致其强度变弱\", \"relatedPart\", \"塑料活塞销\"],\n"
        "      [\"更换为金属活塞销\", \"belongsToReport\", \"EP2002阀二级调节器压力超差故障8D分析报告\"],\n"
        "      [\"更换为金属活塞销\", \"verifiesCause\", \"塑料活塞销存在气孔导致其强度变弱\"],\n"
        "      [\"更换为金属活塞销\", \"targetPart\", \"塑料活塞销\"],\n"
        "      [\"BOM上活塞销材料由塑料改为金属\", \"belongsToReport\", \"EP2002阀二级调节器压力超差故障8D分析报告\"],\n"
        "      [\"BOM上活塞销材料由塑料改为金属\", \"targetPart\", \"塑料活塞销\"],\n"
        "      [\"塑料活塞销\", \"suppliedBy\", \"富士康\"]\n"
        "    ]\n"
        "  }\n"
        "}\n"
    )

    template_en = template_zh
