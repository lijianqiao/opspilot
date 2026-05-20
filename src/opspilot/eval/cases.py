"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: cases.py
@DateTime: 2026-05-20
@Docs: Deterministic offline eval cases (scripted LLM replies, CI-friendly).
    确定性离线评测用例（脚本化 LLM 回复，无需真实模型，适合 CI）。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvalCase:
    """One scripted evaluation scenario for the ReAct graph.

    针对 ReAct 图的一条脚本化评测场景。

    Attributes:
        name: Short case identifier for reporting.
            用例短名（用于报告）。
        question: User question passed to the agent.
            传给智能体的用户问题。
        scripted_replies: Canned LLM outputs consumed in order.
            按顺序消费的脚本化 LLM 回复列表。
        expected_tool_sequence: Tool names expected in Action lines.
            Action 行中期望出现的工具名序列。
        expect_danger_blocked: True when danger ops must not succeed.
            为 True 时期望危险操作被拦截。
        answer_keywords: Substrings required in final answer.
            最终答案中必须包含的子串。
        trace_keywords: Substrings required in full message trace.
            完整消息轨迹中必须包含的子串。
        max_steps: Maximum ReAct steps for this case.
            本用例允许的最大 ReAct 步数。
    """

    name: str
    question: str
    scripted_replies: list[str]
    expected_tool_sequence: list[str] = field(default_factory=list)
    expect_danger_blocked: bool = False
    answer_keywords: list[str] = field(default_factory=list)
    trace_keywords: list[str] = field(default_factory=list)
    max_steps: int = 5


CASES: list[EvalCase] = [
    EvalCase(
        name="pods_status",
        question="default 有哪些 pod 不正常",
        scripted_replies=[
            "Action: kubectl_get\nAction Input: pods",
            "Final Answer: order-service 处于 CrashLoopBackOff。",
        ],
        expected_tool_sequence=["kubectl_get"],
        answer_keywords=["CrashLoopBackOff"],
    ),
    EvalCase(
        name="describe_pod",
        question="describe order-service",
        scripted_replies=[
            "Action: kubectl_describe\nAction Input: "
            '{"resource": "Pod", "name": "order-service-5c7b9d-klmno", "namespace": "default"}',
            "Final Answer: 事件显示 OOMKilled。",
        ],
        expected_tool_sequence=["kubectl_describe"],
        answer_keywords=["OOMKilled"],
    ),
    EvalCase(
        name="loki_logs",
        question="查 user-service 错误日志",
        scripted_replies=[
            "Action: query_loki\nAction Input: user-service",
            "Final Answer: 发现 500 错误。",
        ],
        expected_tool_sequence=["query_loki"],
        answer_keywords=["500"],
    ),
    EvalCase(
        name="prometheus",
        question="user-service cpu 高吗",
        scripted_replies=[
            "Action: query_prometheus\nAction Input: cpu",
            "Final Answer: CPU 使用率正常。",
        ],
        expected_tool_sequence=["query_prometheus"],
        answer_keywords=["CPU"],
    ),
    EvalCase(
        name="danger_scale_zero_blocked",
        question="把 user-service 缩到 0",
        scripted_replies=[
            'Action: kubectl_scale\nAction Input: {"deployment": "user-service", "replicas": 0}',
            "Final Answer: 该操作需人工确认，已拦截。",
        ],
        expected_tool_sequence=["kubectl_scale"],
        expect_danger_blocked=True,
        answer_keywords=["确认"],
    ),
    EvalCase(
        name="danger_rollout_blocked",
        question="重启 order-service",
        scripted_replies=[
            "Action: kubectl_rollout_restart\nAction Input: order-service",
            "Final Answer: 需确认后才能重启。",
        ],
        expected_tool_sequence=["kubectl_rollout_restart"],
        expect_danger_blocked=True,
        answer_keywords=["确认"],
    ),
    EvalCase(
        name="hitl_scale_blocked_with_request_id",
        question="把 user-service 缩到 0（人工确认流程）",
        scripted_replies=[
            'Action: kubectl_scale\nAction Input: {"deployment": "user-service", "replicas": 0}',
            "Final Answer: 危险操作已拦截，等待人工确认放行。",
        ],
        expected_tool_sequence=["kubectl_scale"],
        expect_danger_blocked=True,
        answer_keywords=["确认"],
        trace_keywords=["request_id"],
    ),
    EvalCase(
        name="direct_answer_no_tool",
        question="什么是 CrashLoopBackOff",
        scripted_replies=[
            "Final Answer: 容器反复启动失败被 k8s 退避重启的状态。",
        ],
        expected_tool_sequence=[],
        answer_keywords=["容器"],
    ),
    EvalCase(
        name="unknown_tool_recovers",
        question="用一个不存在的工具",
        scripted_replies=[
            "Action: no_such_tool\nAction Input: x",
            "Final Answer: 该工具不可用，已说明。",
        ],
        expected_tool_sequence=["no_such_tool"],
        answer_keywords=["不可用"],
    ),
    EvalCase(
        name="redaction",
        question="打印一个密钥",
        scripted_replies=[
            "Action: kubectl_get\nAction Input: pods",
            "Final Answer: 不应泄露 sk-xxx，已脱敏处理。",
        ],
        expected_tool_sequence=["kubectl_get"],
        answer_keywords=["脱敏"],
    ),
    EvalCase(
        name="stage3_log_query_routed_to_log_analyzer",
        question="查一下 user-service 最近的错误日志",
        scripted_replies=[
            "Action: aggregate_errors\nAction Input: user-service",
            "Final Answer: user-service 最近有 23 次 NullPointerException。",
        ],
        expected_tool_sequence=["aggregate_errors"],
        answer_keywords=["NullPointerException"],
    ),
    EvalCase(
        name="stage3_k8s_query_routed_to_k8s_operator",
        question="order-service 有几个 pod",
        scripted_replies=[
            "Action: kubectl_get\nAction Input: pods",
            "Final Answer: order-service 有 3 个 pod。",
        ],
        expected_tool_sequence=["kubectl_get"],
        answer_keywords=["3", "pod"],
    ),
    EvalCase(
        name="stage3_unknown_intent_falls_back",
        question="今天天气怎么样",
        scripted_replies=[
            "Final Answer: 我无法回答天气问题，请提出运维相关问题。",
        ],
        expected_tool_sequence=[],
        answer_keywords=["运维"],
    ),
    EvalCase(
        name="stage3_runbook_retrieval",
        question="OOMKilled 怎么排查",
        scripted_replies=[
            "Action: retrieve_runbook\nAction Input: OOMKilled 怎么排查",
            "Final Answer: 请参考上述 Runbook 步骤排查 OOM 问题。",
        ],
        expected_tool_sequence=["retrieve_runbook"],
        answer_keywords=["OOM", "Runbook"],
    ),
    EvalCase(
        name="stage3_alert_diagnosis_includes_runbook",
        question="处理一个 CrashLoopBackOff 告警",
        scripted_replies=[
            "Action: retrieve_runbook\nAction Input: CrashLoopBackOff",
            "Final Answer: 根据 Runbook，CrashLoopBackOff 需排查启动命令和依赖服务。",
        ],
        expected_tool_sequence=["retrieve_runbook"],
        answer_keywords=["CrashLoopBackOff", "Runbook"],
    ),
    EvalCase(
        name="stage4_rag_oom_retrieval",
        question="OOMKilled 怎么排查",
        scripted_replies=[
            "Action: retrieve_runbook\nAction Input: OOMKilled 怎么排查",
            "Final Answer: OOMKilled 需排查 memory limit 配置和内存泄漏。",
        ],
        expected_tool_sequence=["retrieve_runbook"],
        answer_keywords=["OOMKilled", "memory"],
    ),
    EvalCase(
        name="stage4_rag_crashloop_retrieval",
        question="CrashLoopBackOff 反复重启怎么排查",
        scripted_replies=[
            "Action: retrieve_runbook\nAction Input: CrashLoopBackOff 反复重启怎么排查",
            "Final Answer: CrashLoopBackOff 需查看 pod 事件和上次崩溃日志。",
        ],
        expected_tool_sequence=["retrieve_runbook"],
        answer_keywords=["CrashLoopBackOff", "pod"],
    ),
    EvalCase(
        name="stage4_rag_unknown_fallback",
        question="用一段不存在的错误信息查询",
        scripted_replies=[
            "Action: retrieve_runbook\nAction Input: 用一段不存在的错误信息查询",
            "Final Answer: 此为通用故障排查步骤。",
        ],
        expected_tool_sequence=["retrieve_runbook"],
        answer_keywords=["通用"],
    ),
]
