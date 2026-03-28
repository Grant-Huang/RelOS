"""
relos/decision/workflow.py
--------------------------
LangGraph 决策工作流：LLM 融合根因分析。

工作流节点（设计文档 §6.1）：
  [start]
    ↓
  extract_context     → 调用 Context Engine，编译子图为 Prompt block
    ↓
  check_rule_engine   → 高置信度关系直接走规则，不消耗 LLM Token
    ↓ (only if rules insufficient)
  llm_analyze         → 调用 Claude，附带关系上下文
    ↓
  evaluate_hitl       → 判断是否触发 Human-in-the-Loop
    ↓
  [end] → RootCauseRecommendation

设计约束：
- 规则引擎优先（节省 Token，响应更快）
- LLM 只处理规则引擎无法覆盖的不确定场景
- Human-in-the-Loop 在六种明确条件下触发
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from relos.config import settings
from relos.context.compiler import ContextBlock, ContextCompiler
from relos.core.models import RelationObject

# LLM 调用超时（秒）：超出后自动降级 HITL（UX Flow §6.4）
LLM_TIMEOUT_SECONDS = 15

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────
# 工作流状态（贯穿所有节点）
# ─────────────────────────────────────────────

class DecisionState(TypedDict):
    """LangGraph 工作流的共享状态对象。"""

    # 输入
    alarm_id: str
    device_id: str
    alarm_code: str
    alarm_description: str
    severity: str
    relations: list[RelationObject]

    # 中间状态
    context_block: ContextBlock | None
    avg_confidence: float
    engine_path: Literal["rule_engine", "llm", "hitl", "none"]

    # 中间标志
    _rule_engine_no_match: bool

    # 输出
    recommended_cause: str
    confidence: float
    reasoning: str
    supporting_relation_ids: list[str]
    requires_human_review: bool
    error: str | None


# ─────────────────────────────────────────────
# 节点函数
# ─────────────────────────────────────────────

def node_extract_context(state: DecisionState) -> dict[str, Any]:
    """
    节点 1：提取子图，编译为 Prompt 上下文。
    计算子图平均置信度，决定后续走哪条路径。
    """
    # force_hitl：API 层在 initial_state.engine_path 预置为 "hitl"
    # 工作流必须尊重该强制路径，不能被后续分支覆盖。
    forced_hitl = state.get("engine_path") == "hitl"
    relations = state["relations"]

    if not relations:
        return {
            "context_block": None,
            "avg_confidence": 0.0,
            "engine_path": "hitl" if forced_hitl else "none",
        }

    # 编译子图为 Prompt block
    compiler = ContextCompiler(max_relations=15, token_budget=1500)  # 设计规格：architecture.md §3.3  # noqa: E501
    context_block = compiler.compile(
        relations=relations,
        center_node_id=state["device_id"],
        query_context=f"告警码: {state['alarm_code']} | {state['alarm_description']}",
    )

    # 加权平均置信度（直接关联节点权重 x2）
    direct = [
        r for r in relations
        if state["device_id"] in (r.source_node_id, r.target_node_id)
    ]
    indirect = [r for r in relations if r not in direct]

    weighted_sum = sum(r.confidence * 2 for r in direct) + sum(r.confidence for r in indirect)
    total_weight = len(direct) * 2 + len(indirect)
    avg_conf = weighted_sum / total_weight if total_weight > 0 else 0.0

    # ─── 决定引擎路径（含全部六条 HITL 规则）────────────────────────
    # 规则 2：critical 告警且无高置信度（≥0.75）关系 → HITL
    has_high_conf = any(r.confidence >= settings.RULE_ENGINE_MIN_CONFIDENCE for r in relations)
    critical_force_hitl = (
        state.get("severity", "") == "critical" and not has_high_conf
    )

    # 规则 3：冲突关系数量 > 2 → HITL
    conflict_count = sum(1 for r in relations if r.conflict_with)
    conflict_force_hitl = conflict_count > 2

    if forced_hitl:
        path: Literal["rule_engine", "llm", "hitl", "none"] = "hitl"
    elif critical_force_hitl or conflict_force_hitl:
        path: Literal["rule_engine", "llm", "hitl", "none"] = "hitl"
    elif avg_conf >= settings.RULE_ENGINE_MIN_CONFIDENCE:
        path = "rule_engine"
    elif avg_conf < settings.HITL_TRIGGER_CONFIDENCE:
        path = "hitl"
    else:
        path = "llm"

    logger.info(
        "context_extracted",
        alarm_id=state["alarm_id"],
        relation_count=context_block.relation_count,
        avg_confidence=round(avg_conf, 3),
        engine_path=path,
    )

    return {
        "context_block": context_block,
        "avg_confidence": round(avg_conf, 3),
        "engine_path": path,
    }


def node_rule_engine(state: DecisionState) -> dict[str, Any]:
    """
    节点 2a：规则引擎路径。
    基于高置信度关系直接推断根因，零 LLM Token 消耗。

    规则库（MVP 版本）：
    - 关系置信度 >= 0.8 且 relation_type 包含 INDICATES → 直接采用作为根因
    - 有历史频率属性（frequency_6month）→ 计入推荐理由
    """
    relations = state["relations"]
    alarm_code = state["alarm_code"]

    # 筛选高置信度的指示性关系（使用配置阈值，与路由层保持一致）
    indicates_rels = [
        r for r in relations
        if "INDICATES" in r.relation_type and r.confidence >= settings.RULE_ENGINE_MIN_CONFIDENCE
    ]
    indicates_rels.sort(key=lambda r: r.confidence, reverse=True)

    if indicates_rels:
        top = indicates_rels[0]
        freq = top.properties.get("frequency_6month", "")
        freq_text = f"（近 6 个月触发 {freq} 次）" if freq else ""

        cause = f"{top.target_node_id} 异常{freq_text}"
        reasoning = (
            f"规则引擎基于 {len(indicates_rels)} 条指示性关系推断，"
            f"最高置信度关系：{top.relation_type}，置信度 {top.confidence:.2f}。"
            f"来源：{top.provenance_detail or top.provenance.value}"
        )
        return {
            "recommended_cause": cause,
            "confidence": top.confidence,
            "reasoning": reasoning,
            "supporting_relation_ids": [r.id for r in indicates_rels[:3]],
            "requires_human_review": False,
        }

    # 无指示性关系：降级到 LLM（规则 5 的前半部分）
    logger.info("rule_engine_no_match", alarm_code=alarm_code, fallback="llm")
    return {"engine_path": "llm", "_rule_engine_no_match": True}


async def node_llm_analyze(state: DecisionState) -> dict[str, Any]:
    """
    节点 2b：LLM 融合分析路径。
    将 Context Engine 编译的子图上下文注入 Claude，获取根因推断。

    Prompt 设计原则（设计文档 §6.3）：
    - System prompt 包含角色定义 + 关系上下文
    - User prompt 是当前告警描述
    - 要求 LLM 输出结构化 JSON（根因 + 置信度 + 推理链）
    """
    import anthropic

    context_block = state["context_block"]
    if context_block is None:
        return {
            "recommended_cause": "无上下文数据，无法分析",
            "confidence": 0.0,
            "reasoning": "Context Engine 未返回有效子图。",
            "supporting_relation_ids": [],
            "requires_human_review": True,
        }

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    system_prompt = f"""你是一位工业设备故障诊断专家，配备了来自工厂关系图谱的历史知识。
你的任务是根据提供的关系上下文，分析设备告警的最可能根因。

{context_block.content}

## 输出格式要求
请严格按照以下 JSON 格式输出，不要有任何其他文字：
{{
  "recommended_cause": "根因描述（30 字以内，面向维修工程师）",
  "confidence": 0.0-1.0之间的数字,
  "reasoning": "推理过程（100 字以内，说明你依据哪些关系得出结论）",
  "supporting_relation_types": ["关系类型1", "关系类型2"]
}}

## 约束
- confidence 必须反映你对结论的真实把握程度，不要虚高
- 如果关系数据不足以得出确定结论，confidence 应低于 0.5
- recommended_cause 必须是维修工程师可以直接采取行动的具体描述"""

    user_message = (
        f"设备告警信息：\n"
        f"- 告警码：{state['alarm_code']}\n"
        f"- 告警描述：{state['alarm_description']}\n"
        f"- 严重程度：{state['severity']}\n\n"
        f"请分析根因。"
    )

    import json

    try:
        # D-04 修复：强制超时 LLM_TIMEOUT_SECONDS 秒，超出自动降级 HITL（UX Flow §6.4）
        response = await asyncio.wait_for(
            client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=512,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )

        raw = response.content[0].text.strip()
        parsed = json.loads(raw)

        # 安全：LLM 输出的置信度上限 0.85（与 RelationObject 的 LLM 约束一致）
        llm_confidence = min(float(parsed.get("confidence", 0.5)), 0.85)

        logger.info(
            "llm_analysis_complete",
            alarm_id=state["alarm_id"],
            llm_confidence=llm_confidence,
            tokens_used=response.usage.input_tokens + response.usage.output_tokens,
        )

        # D-02 规则 5：规则引擎无匹配 + LLM confidence < 0.4 → HITL
        rule_engine_no_match = state.get("_rule_engine_no_match", False)
        force_hitl_rule5 = rule_engine_no_match and llm_confidence < 0.4

        return {
            "recommended_cause": parsed.get("recommended_cause", "LLM 未给出明确根因"),
            "confidence": llm_confidence,
            "reasoning": parsed.get("reasoning", ""),
            "supporting_relation_ids": [],
            "requires_human_review": (
                force_hitl_rule5 or llm_confidence < settings.HITL_TRIGGER_CONFIDENCE
            ),
        }

    except TimeoutError:
        logger.warning(
            "llm_timeout",
            alarm_id=state["alarm_id"],
            timeout_seconds=LLM_TIMEOUT_SECONDS,
            note="自动降级到 HITL（UX Flow §6.4）",
        )
        return {
            "recommended_cause": "LLM 分析超时，已加入人工审核队列",
            "confidence": 0.0,
            "reasoning": f"AI 分析超过 {LLM_TIMEOUT_SECONDS}s，已自动降级为 HITL。",
            "supporting_relation_ids": [],
            "requires_human_review": True,
            "error": "llm_timeout",
        }
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("llm_parse_error", error=str(e))
        return {
            "recommended_cause": "LLM 分析结果格式异常，需人工审核",
            "confidence": 0.0,
            "reasoning": f"LLM 返回了无法解析的结果：{str(e)}",
            "supporting_relation_ids": [],
            "requires_human_review": True,
        }
    except Exception as e:
        logger.error("llm_call_failed", error=str(e))
        return {
            "recommended_cause": "LLM 服务暂时不可用",
            "confidence": 0.0,
            "reasoning": f"API 调用失败：{str(e)[:100]}",
            "supporting_relation_ids": [],
            "requires_human_review": True,
            "error": str(e),
        }


def node_hitl(state: DecisionState) -> dict[str, Any]:
    """
    节点 2c：Human-in-the-Loop 路径。

    HITL 触发条件（设计文档 §6.2，六条明确规则）：
    1. 子图平均置信度 < HITL_TRIGGER_CONFIDENCE (0.5)
    2. 告警级别为 critical 且无高置信度历史关系
    3. 冲突关系数量 > 2
    4. 图中无数据（新设备 / 新告警类型）
    5. 规则引擎无匹配 + LLM confidence < 0.4
    6. 工程师手动触发（API 参数）
    """
    relations = state["relations"]
    conflict_count = sum(1 for r in relations if r.conflict_with)

    # 生成 HITL 触发原因说明
    reasons: list[str] = []
    if state["avg_confidence"] < settings.HITL_TRIGGER_CONFIDENCE:
        reasons.append(f"关系图谱平均置信度 {state['avg_confidence']:.2f} 低于阈值")
    if not relations:
        reasons.append("设备在 RelOS 中暂无历史关系记录")
    if conflict_count > 2:
        reasons.append(f"存在 {conflict_count} 条冲突关系，需人工裁决")
    if state["severity"] == "critical":
        reasons.append("告警级别 critical，强制人工确认")

    reason_text = "；".join(reasons) if reasons else "系统判断置信度不足"

    return {
        "engine_path": "hitl",
        "recommended_cause": "需人工诊断",
        "confidence": state["avg_confidence"],
        "reasoning": (
            f"HITL 触发原因：{reason_text}。\n"
            f"相关关系数量：{len(relations)} 条。"
            f"请工程师查阅 /v1/relations/pending-review 并补充知识。"
        ),
        "supporting_relation_ids": [r.id for r in relations[:5]],
        "requires_human_review": True,
    }


def node_no_data(state: DecisionState) -> dict[str, Any]:
    """节点 2d：无数据路径（新设备或图谱为空）。"""
    return {
        "engine_path": "no_data",
        "recommended_cause": "无历史数据，需人工诊断并录入关系",
        "confidence": 0.0,
        "reasoning": (
            f"设备 {state['device_id']} 在 RelOS 图谱中暂无关联关系。\n"
            "建议：运行专家初始化（/v1/expert-init），录入设备历史知识。"
        ),
        "supporting_relation_ids": [],
        "requires_human_review": True,
    }


# ─────────────────────────────────────────────
# 路由函数（条件边）
# ─────────────────────────────────────────────

def route_by_engine_path(state: DecisionState) -> str:
    """根据 engine_path 路由到不同的分析节点。"""
    path = state.get("engine_path", "none")
    return {
        "rule_engine": "rule_engine",
        "llm": "llm_analyze",
        "hitl": "hitl",
        "none": "no_data",
    }.get(path, "hitl")


def route_after_rule_engine(state: DecisionState) -> str:
    """规则引擎未匹配时，降级到 LLM。"""
    # 如果规则引擎将 engine_path 改为 llm，则走 llm
    if state.get("engine_path") == "llm":
        return "llm_analyze"
    return END


# ─────────────────────────────────────────────
# 工作流构建
# ─────────────────────────────────────────────

def build_decision_workflow() -> Any:
    """
    构建并编译 LangGraph 决策工作流。

    图结构：
        extract_context
              ↓ (route)
      ┌───────┼──────────┬──────────┐
    rule_engine  llm_analyze  hitl  no_data
      ↓ (match)    ↓          ↓       ↓
      END       END         END     END
      ↓ (no match → llm)
    llm_analyze → END
    """
    workflow = StateGraph(DecisionState)

    # 注册节点
    workflow.add_node("extract_context", node_extract_context)
    workflow.add_node("rule_engine", node_rule_engine)
    workflow.add_node("llm_analyze", node_llm_analyze)
    workflow.add_node("hitl", node_hitl)
    workflow.add_node("no_data", node_no_data)

    # 入口
    workflow.set_entry_point("extract_context")

    # 条件路由：extract_context → {rule_engine | llm_analyze | hitl | no_data}
    workflow.add_conditional_edges(
        "extract_context",
        route_by_engine_path,
        {
            "rule_engine": "rule_engine",
            "llm_analyze": "llm_analyze",
            "hitl": "hitl",
            "no_data": "no_data",
        },
    )

    # 规则引擎可能降级到 LLM
    workflow.add_conditional_edges(
        "rule_engine",
        route_after_rule_engine,
        {"llm_analyze": "llm_analyze", END: END},
    )

    # 终止节点
    workflow.add_edge("llm_analyze", END)
    workflow.add_edge("hitl", END)
    workflow.add_edge("no_data", END)

    return workflow.compile()


# 模块级单例（应用启动时构建一次）
_workflow_instance: Any = None


def get_decision_workflow() -> Any:
    """获取（懒加载）编译好的工作流实例。"""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = build_decision_workflow()
    return _workflow_instance
