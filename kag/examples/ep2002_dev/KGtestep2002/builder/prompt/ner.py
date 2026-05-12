# -*- coding: utf-8 -*-
"""
KGtestep2002 项目自定义 NER prompt。
继承 KAG 内置的 SPGEntityPrompt：基类会自动从 SchemaClient 加载 schema，
把所有 EntityType + desc + properties 渲染到 prompt 的 schema 字段。
我们只需要：
  1) 重写 instruction，加上"白名单类型 + 禁止新创类型"的硬约束
  2) 重写 example，换成 8D 报告领域的示例
  3) 通过 @PromptABC.register 起一个新名字 "kgtest_ner"，在 yaml 里引用
"""

from kag.interface import PromptABC
from kag.builder.prompt.spg_prompt import SPGEntityPrompt


# 白名单：必须与 schema/KGtestep2002.schema 中的 EntityType 完全一致
ALLOWED_TYPES = [
    "ProductModel", "ProductInstance", "BOMPart", "PartSerial",
    "Installation", "ProductEvent", "EightDReport", "CauseItem",
    "ActionItem", "FailureMode", "EventCategory", "Organization",
]

ALLOWED_TYPES_STR = "、".join(ALLOWED_TYPES)


@PromptABC.register("kgtest_ner")
class KGTestNERPrompt(SPGEntityPrompt):

    template_zh: dict = {
        "instruction": (
            "你是一名工业产品质量领域(8D报告)的图谱抽取专家。\n"
            "请严格按照 schema 字段中给出的实体类型和属性，从 input 文本中抽取实体。\n"
            "硬性要求:\n"
            "1) category 字段只能取以下白名单中的英文类型名,严禁新创类型,严禁出现 "
            "Document/Product/Component/Vehicle/Customer/Issue/Project/Evidence 等不在白名单的类型: "
            f"{ALLOWED_TYPES_STR}。\n"
            "2) 如果文本中出现的事物不属于白名单中的任何一类,直接忽略,不要编造。\n"
            "3) 'EP2002阀'是 ProductModel(产品型号),不是 ProductInstance;只有写明序列号/出厂号的具体机器才是 ProductInstance。\n"
            "4) '塑料活塞销/弹簧/阀座/进气口/二级调节器'等零件名属于 BOMPart(设计件);"
            "只有出现具体序列号/批次号的实物零件才是 PartSerial。\n"
            "5) '客户/供应商/事业部/项目组'统一抽为 Organization,通过 orgType 区分,不要建 Customer/Supplier 类型。\n"
            "6) '8D报告/8D分析报告/问题分析报告'统一抽为 EightDReport;同一份报告(同 reportNo 或标题相近)在不同段落出现时,"
            "应输出同一个 name,以便后续合并。\n"
            "7) '根本原因/中间原因/直接原因'都抽为 CauseItem,通过 causeType 区分;\n"
            "   '临时措施/纠正措施/预防措施/根因分析任务'都抽为 ActionItem,通过 actionType 区分。\n"
            "8) '压力超差/压力超限/压力偏差'等同义失效现象,统一为 FailureMode,name 取最规范的一种(如'压力超差')。\n"
            "9) properties 必须包含 name 字段,值为该实体的中文规范名;无法提取的属性返回 null,List 类型返回 list。\n"
            "10) 输出严格的 JSON list 格式,不要任何解释、不要 markdown 代码块、不要思考过程。\n"
            "schema:\n$schema\n\ninput:\n$input"
        ),
        "example": [
            {
                "input": (
                    "EP2002阀二级调节器压力超差故障8D分析报告(报告号:8D-2022-0814):\n"
                    "D2 问题描述:2022年8月14日,客户A在使用过程中发现EP2002阀的二级调节器实际输出压力低于规格下限,出现压力超差现象。\n"
                    "D4 根本原因:塑料活塞销存在气孔导致其强度变弱(根本原因)。\n"
                    "中间原因 1:活塞销强度变弱后,在弹簧持续作用下发生变形;\n"
                    "中间原因 2:活塞销变形导致进气口闭合时受到的弹簧应力变小,进气压力随之变小。\n"
                    "D5 永久纠正措施:更换为金属活塞销,加严批次进货检验。\n"
                    "D7 防再发:在 BOM 上将活塞销材料由塑料变更为金属。"
                ),
                "output": [
                    {
                        "category": "EightDReport",
                        "properties": {
                            "name": "EP2002阀二级调节器压力超差故障8D分析报告",
                            "reportNo": "8D-2022-0814",
                            "issueTitle": "EP2002阀二级调节器压力超差故障",
                            "d2ProblemStatement": "EP2002阀二级调节器实际输出压力低于规格下限,出现压力超差",
                            "d4RootCauseSummary": "塑料活塞销存在气孔导致其强度变弱",
                            "d5PermanentCorrectionSummary": "更换为金属活塞销,加严批次进货检验",
                            "d7PreventionSummary": "BOM 上将活塞销材料由塑料变更为金属"
                        }
                    },
                    {
                        "category": "ProductModel",
                        "properties": {"name": "EP2002阀", "modelCode": "EP2002"}
                    },
                    {
                        "category": "BOMPart",
                        "properties": {"name": "二级调节器", "partType": "组件"}
                    },
                    {
                        "category": "BOMPart",
                        "properties": {"name": "塑料活塞销", "partType": "零件"}
                    },
                    {
                        "category": "BOMPart",
                        "properties": {"name": "弹簧", "partType": "零件"}
                    },
                    {
                        "category": "BOMPart",
                        "properties": {"name": "进气口", "partType": "零件"}
                    },
                    {
                        "category": "FailureMode",
                        "properties": {"name": "压力超差"}
                    },
                    {
                        "category": "ProductEvent",
                        "properties": {
                            "name": "EP2002阀二级调节器压力超差事件",
                            "eventType": "故障",
                            "symptom": "二级调节器实际输出压力低于规格下限",
                            "eventTime": "2022-08-14",
                            "severity": None
                        }
                    },
                    {
                        "category": "CauseItem",
                        "properties": {
                            "title": "塑料活塞销存在气孔导致其强度变弱",
                            "name": "塑料活塞销存在气孔导致其强度变弱",
                            "causeType": "根本原因",
                            "isVerified": None
                        }
                    },
                    {
                        "category": "CauseItem",
                        "properties": {
                            "title": "活塞销强度变弱后在弹簧作用下发生变形",
                            "name": "活塞销强度变弱后在弹簧作用下发生变形",
                            "causeType": "中间原因"
                        }
                    },
                    {
                        "category": "CauseItem",
                        "properties": {
                            "title": "活塞销变形导致进气压力变小",
                            "name": "活塞销变形导致进气压力变小",
                            "causeType": "中间原因"
                        }
                    },
                    {
                        "category": "ActionItem",
                        "properties": {
                            "title": "更换为金属活塞销",
                            "name": "更换为金属活塞销",
                            "actionType": "纠正措施"
                        }
                    },
                    {
                        "category": "ActionItem",
                        "properties": {
                            "title": "加严活塞销批次进货检验",
                            "name": "加严活塞销批次进货检验",
                            "actionType": "纠正措施"
                        }
                    },
                    {
                        "category": "ActionItem",
                        "properties": {
                            "title": "BOM上活塞销材料由塑料改为金属",
                            "name": "BOM上活塞销材料由塑料改为金属",
                            "actionType": "预防措施"
                        }
                    },
                    {
                        "category": "Person",
                        "properties": {"name": "王怀亮", "role": "质量工程师"}
                    },
                    {
                        "category": "Organization",
                        "properties": {"name": "客户A", "orgType": "客户"}
                    },
                    {
                        "category": "Organization",
                        "properties": {"name": "调节器事业部", "orgType": "部门"}
                    }
                ]
            }
        ],
    }

    # 项目是中文 8D 报告,直接复用中文模板即可
    template_en: dict = template_zh
