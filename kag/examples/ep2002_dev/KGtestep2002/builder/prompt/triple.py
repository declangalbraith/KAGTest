# -*- coding: utf-8 -*-
"""
KGtestep2002 项目自定义关系(三元组)抽取 prompt。
要求 LLM 只输出 schema 中已定义的具名关系(白名单),
头/尾实体只能取自上一步 NER 已识别出的实体列表(由 KAG 注入到 input 中)。

本版本对应"精简后的 schema":
  - 已删除所有以 Person / Location 为头或尾类型的关系
  - 人员/地点信息以属性形式存在,不再通过关系连接
"""

from kag.interface import PromptABC
from kag.builder.prompt.spg_prompt import SPGPrompt


# 白名单:与 schema 中所有 EntityType 的 relations 完全对齐。
# 每条形如 (头类型, 关系英文名, 尾类型, 关系中文名)
ALLOWED_RELATIONS = [
    # ProductModel
    ("ProductModel", "manufacturer", "Organization", "制造商"),
    ("ProductModel", "hasBOMPart", "BOMPart", "包含BOM件"),
    ("ProductModel", "hasBOMRoot", "BOMPart", "根BOM"),
    ("ProductModel", "hasInstance", "ProductInstance", "产品实例"),

    # ProductInstance (已删除 locatedAt -> Location)
    ("ProductInstance", "basedOnModel", "ProductModel", "对应型号"),
    ("ProductInstance", "has8D", "EightDReport", "关联8D"),
    ("ProductInstance", "hasInstallation", "Installation", "安装记录"),
    ("ProductInstance", "hasCurrentPart", "PartSerial", "当前安装件"),
    ("ProductInstance", "hasEvent", "ProductEvent", "发生事件"),
    ("ProductInstance", "ownedBy", "Organization", "所属客户"),

    # BOMPart
    ("BOMPart", "parentPart", "BOMPart", "上级BOM件"),
    ("BOMPart", "fulfilledBy", "PartSerial", "对应实例件"),
    ("BOMPart", "childPart", "BOMPart", "下级BOM件"),
    ("BOMPart", "hasFailureMode", "FailureMode", "失效模式"),
    ("BOMPart", "belongsToModel", "ProductModel", "所属型号"),
    ("BOMPart", "alternativePart", "BOMPart", "替代件"),

    # PartSerial
    ("PartSerial", "involvedIn8D", "EightDReport", "关联8D"),
    ("PartSerial", "involvedInEvent", "ProductEvent", "关联事件"),
    ("PartSerial", "replacedBy", "PartSerial", "替换后件"),
    ("PartSerial", "replaces", "PartSerial", "替换前件"),
    ("PartSerial", "instanceOfPart", "BOMPart", "对应设计件"),
    ("PartSerial", "suppliedBy", "Organization", "供应商"),
    ("PartSerial", "installedOn", "ProductInstance", "安装于产品"),

    # Installation (已删除 operator -> Person)
    ("Installation", "product", "ProductInstance", "产品实例"),
    ("Installation", "partSerial", "PartSerial", "实际安装件"),
    ("Installation", "bomPart", "BOMPart", "对应BOM件"),
    ("Installation", "generatedByEvent", "ProductEvent", "来源事件"),

    # ProductEvent (已删除 reportedBy -> Person)
    ("ProductEvent", "happenedOn", "ProductInstance", "发生于产品"),
    ("ProductEvent", "responsibleOrg", "Organization", "责任组织"),
    ("ProductEvent", "relatedFailureMode", "FailureMode", "关联失效模式"),
    ("ProductEvent", "category", "EventCategory", "事件分类"),
    ("ProductEvent", "relatedInstallation", "Installation", "关联安装记录"),
    ("ProductEvent", "relatedSerial", "PartSerial", "关联序列件"),
    ("ProductEvent", "relatedPart", "BOMPart", "关联设计件"),
    ("ProductEvent", "has8DReport", "EightDReport", "8D报告"),

    # EightDReport (已删除 owner -> Person)
    ("EightDReport", "sourceEvent", "ProductEvent", "源事件"),
    ("EightDReport", "affectedProduct", "ProductInstance", "影响产品"),
    ("EightDReport", "affectedSerial", "PartSerial", "影响序列件"),
    ("EightDReport", "affectedPart", "BOMPart", "影响设计件"),
    ("EightDReport", "rootCause", "CauseItem", "根因项"),
    ("EightDReport", "correctiveAction", "ActionItem", "纠正措施"),
    ("EightDReport", "preventiveAction", "ActionItem", "预防措施"),
    ("EightDReport", "responsibleOrg", "Organization", "责任组织"),

    # CauseItem
    ("CauseItem", "relatedFailureMode", "FailureMode", "关联失效模式"),
    ("CauseItem", "relatedPart", "BOMPart", "关联设计件"),
    ("CauseItem", "relatedSerial", "PartSerial", "关联序列件"),
    ("CauseItem", "belongsToReport", "EightDReport", "所属8D"),
    ("CauseItem", "relatedEvent", "ProductEvent", "关联事件"),

    # ActionItem (已删除 owner -> Person)
    ("ActionItem", "belongsToReport", "EightDReport", "所属8D"),
    ("ActionItem", "verifiesCause", "CauseItem", "验证原因项"),
    ("ActionItem", "relatedEvent", "ProductEvent", "关联事件"),
    ("ActionItem", "targetSerial", "PartSerial", "作用序列件"),
    ("ActionItem", "targetProduct", "ProductInstance", "作用产品"),
    ("ActionItem", "targetPart", "BOMPart", "作用设计件"),
    ("ActionItem", "responsibleOrg", "Organization", "责任组织"),

    # EventCategory
    ("EventCategory", "parentCategory", "EventCategory", "上级分类"),
]

# 把白名单格式化成 prompt 里要插入的字符串
WHITELIST_LINES = "\n".join(
    f"  - ({h}) -[{p} / {zh}]-> ({t})"
    for h, p, t, zh in ALLOWED_RELATIONS
)


@PromptABC.register("kgtest_triple")
class KGTestTriplePrompt(SPGPrompt):

    template_zh: dict = {
        "instruction": (
            "你是一名工业产品质量领域(8D 报告)的图谱关系抽取专家。\n"
            "input 字段包含一段文本,以及上一步已抽取的实体列表(entity_list)。\n"
            "请基于文本和实体列表,抽取实体之间的关系,并以 JSON list 输出三元组。\n"
            "硬性要求:\n"
            "1) 每个三元组形如 {\"subject\": <头实体名>, \"subject_type\": <头实体类型>, "
            "\"predicate\": <英文关系名>, \"object\": <尾实体名>, \"object_type\": <尾实体类型>}。\n"
            "2) predicate 只能取自下面的关系白名单,严禁使用'涉及/相关/关联到'等通用词,"
            "严禁创造白名单外的关系名。\n"
            "3) 头/尾实体名必须与 entity_list 中已抽出的 name 完全一致;若两个实体不在列表中,"
            "不要凭空生成三元组。\n"
            "4) 头/尾实体类型必须严格匹配关系白名单中规定的类型组合;不匹配则跳过。\n"
            "5) **不要生成涉及 Person 或 Location 的关系**。人员/地点信息已在 NER 阶段以属性形式"
            "(ownerName / reporterName / operatorName / siteCity / siteCountry 等)写入相关实体,不需要再连边。\n"
            "6) 因果链:CauseItem 之间不直接连边;'根本原因 -> 中间原因 -> 直接原因'通过共同的 "
            "EightDReport(belongsToReport) 和 ProductEvent(relatedEvent) 关联,causeType 字段在 NER 阶段已写入。\n"
            "7) 输出严格 JSON list,不要解释、不要 markdown、不要思考过程。\n\n"
            "关系白名单(头类型 -[英文谓词 / 中文名]-> 尾类型):\n"
            f"{WHITELIST_LINES}\n\n"
            "schema:\n$schema\n\ninput:\n$input"
        ),
        "example": [
            {
                "input": (
                    "文本: EP2002阀二级调节器压力超差故障8D分析报告(8D-2022-0814)。"
                    "EP2002阀的制造商是ABB,塑料活塞销由富士康供货。"
                    "事件发生在客户A现场EP2002阀上,失效模式是压力超差。"
                    "根本原因是塑料活塞销存在气孔导致其强度变弱。"
                    "永久纠正措施是更换为金属活塞销;预防措施是BOM上活塞销材料由塑料改为金属。\n"
                    "entity_list: ["
                    "EightDReport=EP2002阀二级调节器压力超差故障8D分析报告, "
                    "ProductModel=EP2002阀, "
                    "ProductInstance=客户A现场EP2002阀, "
                    "BOMPart=二级调节器, BOMPart=塑料活塞销, BOMPart=弹簧, BOMPart=进气口, "
                    "FailureMode=压力超差, "
                    "ProductEvent=EP2002阀二级调节器压力超差事件, "
                    "CauseItem=塑料活塞销存在气孔导致其强度变弱, "
                    "CauseItem=活塞销强度变弱后在弹簧作用下发生变形, "
                    "CauseItem=活塞销变形导致进气压力变小, "
                    "ActionItem=更换为金属活塞销, "
                    "ActionItem=BOM上活塞销材料由塑料改为金属, "
                    "Organization=ABB, Organization=客户A, Organization=富士康, Organization=调节器事业部"
                    "]"
                ),
                "output": [
                    # ProductModel <-> Organization / BOMPart / ProductInstance
                    {"subject": "EP2002阀", "subject_type": "ProductModel",
                     "predicate": "manufacturer",
                     "object": "ABB", "object_type": "Organization"},
                    {"subject": "EP2002阀", "subject_type": "ProductModel",
                     "predicate": "hasBOMPart",
                     "object": "二级调节器", "object_type": "BOMPart"},
                    {"subject": "EP2002阀", "subject_type": "ProductModel",
                     "predicate": "hasInstance",
                     "object": "客户A现场EP2002阀", "object_type": "ProductInstance"},

                    # ProductInstance
                    {"subject": "客户A现场EP2002阀", "subject_type": "ProductInstance",
                     "predicate": "basedOnModel",
                     "object": "EP2002阀", "object_type": "ProductModel"},
                    {"subject": "客户A现场EP2002阀", "subject_type": "ProductInstance",
                     "predicate": "ownedBy",
                     "object": "客户A", "object_type": "Organization"},
                    {"subject": "客户A现场EP2002阀", "subject_type": "ProductInstance",
                     "predicate": "hasEvent",
                     "object": "EP2002阀二级调节器压力超差事件", "object_type": "ProductEvent"},
                    {"subject": "客户A现场EP2002阀", "subject_type": "ProductInstance",
                     "predicate": "has8D",
                     "object": "EP2002阀二级调节器压力超差故障8D分析报告", "object_type": "EightDReport"},

                    # BOMPart 层级与失效模式
                    {"subject": "二级调节器", "subject_type": "BOMPart",
                     "predicate": "belongsToModel",
                     "object": "EP2002阀", "object_type": "ProductModel"},
                    {"subject": "塑料活塞销", "subject_type": "BOMPart",
                     "predicate": "belongsToModel",
                     "object": "EP2002阀", "object_type": "ProductModel"},
                    {"subject": "塑料活塞销", "subject_type": "BOMPart",
                     "predicate": "parentPart",
                     "object": "二级调节器", "object_type": "BOMPart"},
                    {"subject": "塑料活塞销", "subject_type": "BOMPart",
                     "predicate": "hasFailureMode",
                     "object": "压力超差", "object_type": "FailureMode"},
                    {"subject": "二级调节器", "subject_type": "BOMPart",
                     "predicate": "hasFailureMode",
                     "object": "压力超差", "object_type": "FailureMode"},

                    # ProductEvent
                    {"subject": "EP2002阀二级调节器压力超差事件", "subject_type": "ProductEvent",
                     "predicate": "happenedOn",
                     "object": "客户A现场EP2002阀", "object_type": "ProductInstance"},
                    {"subject": "EP2002阀二级调节器压力超差事件", "subject_type": "ProductEvent",
                     "predicate": "relatedFailureMode",
                     "object": "压力超差", "object_type": "FailureMode"},
                    {"subject": "EP2002阀二级调节器压力超差事件", "subject_type": "ProductEvent",
                     "predicate": "relatedPart",
                     "object": "塑料活塞销", "object_type": "BOMPart"},
                    {"subject": "EP2002阀二级调节器压力超差事件", "subject_type": "ProductEvent",
                     "predicate": "has8DReport",
                     "object": "EP2002阀二级调节器压力超差故障8D分析报告", "object_type": "EightDReport"},

                    # EightDReport
                    {"subject": "EP2002阀二级调节器压力超差故障8D分析报告", "subject_type": "EightDReport",
                     "predicate": "sourceEvent",
                     "object": "EP2002阀二级调节器压力超差事件", "object_type": "ProductEvent"},
                    {"subject": "EP2002阀二级调节器压力超差故障8D分析报告", "subject_type": "EightDReport",
                     "predicate": "affectedProduct",
                     "object": "客户A现场EP2002阀", "object_type": "ProductInstance"},
                    {"subject": "EP2002阀二级调节器压力超差故障8D分析报告", "subject_type": "EightDReport",
                     "predicate": "affectedPart",
                     "object": "塑料活塞销", "object_type": "BOMPart"},
                    {"subject": "EP2002阀二级调节器压力超差故障8D分析报告", "subject_type": "EightDReport",
                     "predicate": "rootCause",
                     "object": "塑料活塞销存在气孔导致其强度变弱", "object_type": "CauseItem"},
                    {"subject": "EP2002阀二级调节器压力超差故障8D分析报告", "subject_type": "EightDReport",
                     "predicate": "correctiveAction",
                     "object": "更换为金属活塞销", "object_type": "ActionItem"},
                    {"subject": "EP2002阀二级调节器压力超差故障8D分析报告", "subject_type": "EightDReport",
                     "predicate": "preventiveAction",
                     "object": "BOM上活塞销材料由塑料改为金属", "object_type": "ActionItem"},
                    {"subject": "EP2002阀二级调节器压力超差故障8D分析报告", "subject_type": "EightDReport",
                     "predicate": "responsibleOrg",
                     "object": "调节器事业部", "object_type": "Organization"},

                    # CauseItem 全部归属同一份 8D 报告 + 同一事件
                    {"subject": "塑料活塞销存在气孔导致其强度变弱", "subject_type": "CauseItem",
                     "predicate": "belongsToReport",
                     "object": "EP2002阀二级调节器压力超差故障8D分析报告", "object_type": "EightDReport"},
                    {"subject": "塑料活塞销存在气孔导致其强度变弱", "subject_type": "CauseItem",
                     "predicate": "relatedEvent",
                     "object": "EP2002阀二级调节器压力超差事件", "object_type": "ProductEvent"},
                    {"subject": "塑料活塞销存在气孔导致其强度变弱", "subject_type": "CauseItem",
                     "predicate": "relatedFailureMode",
                     "object": "压力超差", "object_type": "FailureMode"},
                    {"subject": "塑料活塞销存在气孔导致其强度变弱", "subject_type": "CauseItem",
                     "predicate": "relatedPart",
                     "object": "塑料活塞销", "object_type": "BOMPart"},
                    {"subject": "活塞销强度变弱后在弹簧作用下发生变形", "subject_type": "CauseItem",
                     "predicate": "belongsToReport",
                     "object": "EP2002阀二级调节器压力超差故障8D分析报告", "object_type": "EightDReport"},
                    {"subject": "活塞销强度变弱后在弹簧作用下发生变形", "subject_type": "CauseItem",
                     "predicate": "relatedEvent",
                     "object": "EP2002阀二级调节器压力超差事件", "object_type": "ProductEvent"},
                    {"subject": "活塞销变形导致进气压力变小", "subject_type": "CauseItem",
                     "predicate": "belongsToReport",
                     "object": "EP2002阀二级调节器压力超差故障8D分析报告", "object_type": "EightDReport"},
                    {"subject": "活塞销变形导致进气压力变小", "subject_type": "CauseItem",
                     "predicate": "relatedEvent",
                     "object": "EP2002阀二级调节器压力超差事件", "object_type": "ProductEvent"},

                    # ActionItem 归属、验证原因、作用对象
                    {"subject": "更换为金属活塞销", "subject_type": "ActionItem",
                     "predicate": "belongsToReport",
                     "object": "EP2002阀二级调节器压力超差故障8D分析报告", "object_type": "EightDReport"},
                    {"subject": "更换为金属活塞销", "subject_type": "ActionItem",
                     "predicate": "verifiesCause",
                     "object": "塑料活塞销存在气孔导致其强度变弱", "object_type": "CauseItem"},
                    {"subject": "更换为金属活塞销", "subject_type": "ActionItem",
                     "predicate": "targetPart",
                     "object": "塑料活塞销", "object_type": "BOMPart"},
                    {"subject": "BOM上活塞销材料由塑料改为金属", "subject_type": "ActionItem",
                     "predicate": "belongsToReport",
                     "object": "EP2002阀二级调节器压力超差故障8D分析报告", "object_type": "EightDReport"},
                    {"subject": "BOM上活塞销材料由塑料改为金属", "subject_type": "ActionItem",
                     "predicate": "targetPart",
                     "object": "塑料活塞销", "object_type": "BOMPart"},

                    # PartSerial 没在示例中出现,跳过
                ]
            }
        ],
    }

    template_en: dict = template_zh
