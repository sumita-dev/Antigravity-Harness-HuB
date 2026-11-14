"""End-to-End verification of Automatic Skill Activation, PreInvocation Hook, and Task-Aware SubAgent Dispatch."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest

from harness.orchestrator import ChiefOrchestrator
from harness.quality_gate import Verdict
from harness.skills.router import SkillLoader, SkillRouter
from harness.state_machine import HarnessState
from scripts.auto_skill_router_hook import (
    ROUTER_MARKER,
    evaluate_pre_invocation_payload,
)
from scripts.dispatch_subagents import get_all_agents, parse_agent_file

REPO_ROOT = Path(__file__).resolve().parent.parent
PRE_INVOCATION_HOOK_SCRIPT = REPO_ROOT / "scripts" / "auto_skill_router_hook.py"
DISPATCH_SCRIPT = REPO_ROOT / "scripts" / "dispatch_subagents.py"
HARNESS_CONFIG_PATH = REPO_ROOT / "configs" / "harness_config.json"


# =============================================================================
# TEST 1: 100% PHYSICAL SKILL REGISTRY, SLASH ROUTING & PATH VERACITY
# =============================================================================
def test_all_physical_skills_registered_routable_and_loadable() -> None:
    """Every physical SKILL.md under plugins/*/skills/*/SKILL.md must be registered, routable, and loadable."""
    config = json.loads(HARNESS_CONFIG_PATH.read_text(encoding="utf-8"))
    routing_table = config.get("skill_routing", {})
    router = SkillRouter()
    loader = SkillLoader()

    physical_skill_files = sorted((REPO_ROOT / "plugins").glob("*/skills/*/SKILL.md"))
    assert len(physical_skill_files) >= 69, f"Expected >= 69 skills, found {len(physical_skill_files)}"

    for skill_md in physical_skill_files:
        skill_name = skill_md.parent.name
        assert skill_name in routing_table, f"Skill '{skill_name}' missing from configs/harness_config.json"

        entry = routing_table[skill_name]
        assert entry.get("branch") in ("app", "marketing"), f"Invalid branch for {skill_name}"
        keywords = entry.get("keywords", [])
        assert isinstance(keywords, list) and len(keywords) > 0, f"Empty keywords for {skill_name}"

        # Verify physical path resolution and non-empty instructions
        resolved_path = loader.find_skill_path(skill_name)
        assert resolved_path is not None and Path(resolved_path).is_file(), (
            f"SkillLoader could not locate physical SKILL.md for '{skill_name}'"
        )
        instructions = loader.load_instructions(skill_name)
        assert instructions is not None and len(instructions.strip()) > 50, (
            f"Empty or truncated SKILL.md instructions for '{skill_name}'"
        )

        # Verify slash command routing (/skill-name) resolves to canonical target skill
        expected_target = router.resolve_alias(skill_name)
        expected_branch = routing_table.get(expected_target, entry).get("branch")
        routed_skill, routed_branch = router.route(f"/{skill_name}")
        assert routed_skill == expected_target, (
            f"Slash command '/{skill_name}' routed to '{routed_skill}' instead of '{expected_target}'"
        )
        assert routed_branch == expected_branch, (
            f"Slash command '/{skill_name}' routed to branch '{routed_branch}' instead of '{expected_branch}'"
        )


# =============================================================================
# TEST 2: MULTI-DOMAIN PROJECT TASK ROUTING MATRIX
# =============================================================================
MULTI_DOMAIN_ROUTING_MATRIX = [
    # App Branch Tasks
    ("Xây dựng ứng dụng web quản lý kho hàng, làm MVP từ brief", "app", "app"),
    ("Điều tra lỗi tuần tự systematic debugging và tìm root cause analysis cho test failure", "systematic-debugging", "app"),
    ("Kiểm tra bảo mật security review, rà soát lỗ hổng OWASP và SQL injection", "security-review", "app"),
    ("Tối ưu Core Web Vitals, đo LCP, INP, CLS và giảm bundle size cho trang chủ", "webperf", "app"),
    ("Kiểm chứng giao diện verify-ui và chụp màn hình kiểm tra bằng Chrome DevTools MCP", "verify-ui", "app"),
    ("Thiết kế giao diện chuẩn Apple HIG, thực hiện design audit theo apple-inspired-design", "apple-inspired-design", "app"),
    ("Tạo migration database zero-downtime và kế hoạch rollback migration cho bảng users", "database-migrations", "app"),
    ("Viết integration test với Testcontainers PostgreSQL cho tầng repository", "testcontainers", "app"),
    ("Tra cứu wiki về kiến trúc hệ thống trong Second Brain vault", "query-wiki", "app"),
    ("Tiêu hoá source tài liệu kỹ thuật mới vào wiki bằng ingest-source", "ingest-source", "app"),
    ("Chăm sóc máy tính Windows, bảo dưỡng PC và dọn cache Windows", "cham-soc-may-tinh", "app"),
    # Marketing Branch Tasks
    ("Viết kịch bản bóc phốt tài chính theo format Mổ Sổ cho kênh YouTube", "boc-phot-storytelling", "marketing"),
    ("Audit kịch bản tài chính Mỹ cho kênh Broke and Building, kiểm tra bảng lương Mỹ và thuế FICA", "us-finance-script-auditor", "marketing"),
    ("Kiểm tra vi phạm kịch bản và nguyên tắc cộng đồng YouTube YPP trước khi xuất bản", "check-youtube-policy", "marketing"),
    ("Quét thư viện quảng cáo Meta Ad Scout để soi winning ads của đối thủ", "meta-ad-scout", "marketing"),
    ("Tối ưu bài viết chuẩn SEO, AEO và Generative Engine Optimization (GEO)", "viet-content-seo-geo-v5", "marketing"),
    ("Thiết kế Grand Slam Offer và đóng gói combo giá trị theo Alex Hormozi Offer Builder", "alex-hormozi-offer-builder", "marketing"),
    ("Nghiên cứu từ khóa YouTube và chạy SERP audit bằng thuật toán VKOS", "youtube-keyword-intelligence", "marketing"),
]


@pytest.mark.parametrize(("prompt", "expected_skill", "expected_branch"), MULTI_DOMAIN_ROUTING_MATRIX)
def test_multi_domain_project_task_routing(prompt: str, expected_skill: str, expected_branch: str) -> None:
    """Verify realistic user prompts across all project domains route to the exact skill and branch."""
    router = SkillRouter()
    loader = SkillLoader()
    skill, branch = router.route(prompt)
    assert skill == expected_skill, f"Prompt '{prompt}' routed to '{skill}', expected '{expected_skill}'"
    assert branch == expected_branch, f"Prompt '{prompt}' routed to branch '{branch}', expected '{expected_branch}'"
    skill_path = loader.find_skill_path(skill)
    assert skill_path is not None and Path(skill_path).is_file()


# =============================================================================
# TEST 3: PREINVOCATION HOOK END-TO-END CLI EXECUTION & REGISTRATION
# =============================================================================
def _run_pre_invocation_cli(payload: dict[str, Any]) -> dict[str, Any]:
    res = subprocess.run(
        [sys.executable, str(PRE_INVOCATION_HOOK_SCRIPT)],
        input=json.dumps(payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert res.returncode == 0, f"PreInvocation hook failed: {res.stderr}"
    return json.loads(res.stdout.strip())


def test_hooks_json_registers_pre_invocation_auto_skill_router() -> None:
    """Both .agent/hooks.json and .agents/hooks.json must register auto_skill_router_hook.py under PreInvocation."""
    for rel_path in (".agent/hooks.json", ".agents/hooks.json"):
        hooks_path = REPO_ROOT / rel_path
        assert hooks_path.is_file(), f"Missing {rel_path}"
        data = json.loads(hooks_path.read_text(encoding="utf-8"))
        pre_hooks = data.get("auto-code-harvester", {}).get("PreInvocation", [])
        commands = [h.get("command", "") for h in pre_hooks if isinstance(h, dict)]
        assert any("scripts/auto_skill_router_hook.py" in cmd for cmd in commands), (
            f"scripts/auto_skill_router_hook.py not registered in {rel_path}"
        )


def test_pre_invocation_hook_injects_on_initial_turn_and_skips_subsequent_steps() -> None:
    """Verify PreInvocation hook injects skill path & Triad on invocationNum=1 and stays silent on invocationNum=2."""
    # 1. App task on invocationNum=1
    app_payload = {
        "conversationId": "conv-app-1",
        "invocationNum": 1,
        "lastUserInput": "Kiểm tra bảo mật security review và lỗ hổng SQL injection cho API",
    }
    app_out = _run_pre_invocation_cli(app_payload)
    assert app_out["terminationBehavior"] == ""
    assert len(app_out["injectSteps"]) == 1
    app_msg = app_out["injectSteps"][0]["ephemeralMessage"]
    assert ROUTER_MARKER in app_msg
    assert "branch=app" in app_msg
    assert "skill=security-review" in app_msg
    assert "plugins/code/skills/security-review/SKILL.md" in app_msg
    assert "Code Critic (inherit)" in app_msg
    assert "QA Auditor (flash)" in app_msg

    # 2. Marketing task on invocationNum=1
    mkt_payload = {
        "conversationId": "conv-mkt-1",
        "invocationNum": 1,
        "lastUserInput": "Viết kịch bản bóc phốt tài chính cho kênh YouTube",
    }
    mkt_out = _run_pre_invocation_cli(mkt_payload)
    assert len(mkt_out["injectSteps"]) == 1
    mkt_msg = mkt_out["injectSteps"][0]["ephemeralMessage"]
    assert ROUTER_MARKER in mkt_msg
    assert "branch=marketing" in mkt_msg
    assert "skill=boc-phot-storytelling" in mkt_msg
    assert "plugins/marketing/skills/boc-phot-storytelling/SKILL.md" in mkt_msg
    assert "Web Researcher (inherit) -> Creator (inherit) -> Compliance Critic (inherit)" in mkt_msg

    # 3. Subsequent invocation within same turn (invocationNum=2) must NOT re-inject
    step2_payload = {
        "conversationId": "conv-app-1",
        "invocationNum": 2,
        "lastUserInput": "Kiểm tra bảo mật security review và lỗ hổng SQL injection cho API",
    }
    assert evaluate_pre_invocation_payload(step2_payload) == {"injectSteps": [], "terminationBehavior": ""}
    assert _run_pre_invocation_cli(step2_payload) == {"injectSteps": [], "terminationBehavior": ""}

    # 4. Empty input failsafe
    assert _run_pre_invocation_cli({"invocationNum": 1, "lastUserInput": "   "}) == {
        "injectSteps": [],
        "terminationBehavior": "",
    }


# =============================================================================
# TEST 4: SUBAGENT DISPATCH & DYNAMIC TASK SKILL COMPOSITION
# =============================================================================
def test_subagent_dispatch_composes_task_skill_and_enforces_model_tiers() -> None:
    """Verify scripts/dispatch_subagents.py dynamically attaches task-routed skills and enforces explicit model tiers."""
    # 1. App Builder with a database-migrations task via CLI
    res_builder = subprocess.run(
        [
            sys.executable,
            str(DISPATCH_SCRIPT),
            "--export-schema",
            "builder",
            "--task",
            "Tạo migration database zero-downtime và rollback migration",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert res_builder.returncode == 0, res_builder.stderr
    builder_data = json.loads(res_builder.stdout)
    assert builder_data["model"] == "pro"
    assert builder_data["routed_skill"] == "database-migrations"
    assert builder_data["routed_branch"] == "app"
    assert "database-migrations" in builder_data["skill_selection"]["skills"]
    assert "test-driven-development" in builder_data["skill_selection"]["skills"]
    assert builder_data["skill_selection"]["chars"] > 1000

    # 2. Marketing Creator with a boc-phot-storytelling task via CLI
    res_creator = subprocess.run(
        [
            sys.executable,
            str(DISPATCH_SCRIPT),
            "--export-schema",
            "creator",
            "--task",
            "Viết kịch bản bóc phốt tài chính theo format Mổ Sổ",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    assert res_creator.returncode == 0, res_creator.stderr
    creator_data = json.loads(res_creator.stdout)
    assert creator_data["model"] == "pro"
    assert creator_data["routed_skill"] == "boc-phot-storytelling"
    assert creator_data["routed_branch"] == "marketing"
    assert "boc-phot-storytelling" in creator_data["skill_selection"]["skills"]
    assert "cong-thuc-viet-content-by-noti-v4" in creator_data["skill_selection"]["skills"]
    assert creator_data["skill_selection"]["chars"] > 1000

    # 3. Verify Explicit Model Tiering across all Triad roles (Maker/Critic=pro, QA=flash)
    all_agents = get_all_agents(str(REPO_ROOT / "agents"))
    assert all_agents["architect"]["model"] == "pro"
    assert all_agents["design_reviewer"]["model"] == "pro"
    assert all_agents["builder"]["model"] == "pro"
    assert all_agents["code_critic"]["model"] == "pro"
    assert all_agents["qa_auditor"]["model"] == "flash"
    assert all_agents["web_researcher"]["model"] == "pro"
    assert all_agents["creator"]["model"] == "pro"
    assert all_agents["compliance_critic"]["model"] == "pro"


# =============================================================================
# TEST 5: CHIEFORCHESTRATOR END-TO-END TRIAD + SKILL LOAD TRAJECTORY
# =============================================================================
def test_orchestrator_end_to_end_triad_and_skill_load_trajectory() -> None:
    """Verify ChiefOrchestrator routes task, loads physical SKILL.md, executes Triad, and enforces Circuit Breaker."""
    orc = ChiefOrchestrator()

    # 1. App task end-to-end approval
    app_ctx, app_verdict = orc.process_task(
        "Điều tra lỗi tuần tự systematic debugging và tìm root cause cho module thanh toán",
        branch="auto",
    )
    assert app_verdict == Verdict.APPROVE
    assert app_ctx.state == HarnessState.APPROVED
    assert app_ctx.branch == "app"
    assert app_ctx.active_skill == "systematic-debugging"
    assert app_ctx.skill_path is not None and Path(app_ctx.skill_path).is_file()
    assert app_ctx.skill_instructions is not None and len(app_ctx.skill_instructions) > 100

    app_steps = [s["step"] for s in app_ctx.trace_steps]
    assert app_steps == [
        "INTAKE",
        "SKILL_LOAD",
        "DESIGN",
        "IMPLEMENTATION",
        "CRITIQUE",
        "CRITIC",
        "AUDIT",
        "CHECKER",
    ]
    skill_step = next(s for s in app_ctx.trace_steps if s["step"] == "SKILL_LOAD")
    assert skill_step["payload"]["skill"] == "systematic-debugging"
    assert skill_step["payload"]["chars"] > 100

    # 2. Marketing task end-to-end approval
    mkt_ctx, mkt_verdict = orc.process_task(
        "Audit kịch bản tài chính Mỹ cho kênh Broke and Building, kiểm tra thuế FICA",
        branch="auto",
    )
    assert mkt_verdict == Verdict.APPROVE
    assert mkt_ctx.state == HarnessState.APPROVED
    assert mkt_ctx.branch == "marketing"
    assert mkt_ctx.active_skill == "us-finance-script-auditor"
    assert mkt_ctx.skill_path is not None and Path(mkt_ctx.skill_path).is_file()

    mkt_steps = [s["step"] for s in mkt_ctx.trace_steps]
    assert mkt_steps == [
        "INTAKE",
        "SKILL_LOAD",
        "DESIGN",
        "IMPLEMENTATION",
        "CRITIQUE",
        "CRITIC",
        "AUDIT",
        "CHECKER",
    ]
    actors = [s["payload"].get("actor") for s in mkt_ctx.trace_steps if "actor" in s.get("payload", {})]
    assert actors == ["web_researcher", "creator", "content_critic", "compliance_critic"]

    # 3. Circuit Breaker Escalation after 2 rejections
    esc_ctx, esc_verdict = orc.process_task(
        "Kiểm tra bảo mật security review cho cổng thanh toán",
        branch="auto",
        mock_checker_output="VERDICT: REJECT",
        review_rounds=2,
    )
    assert esc_verdict == Verdict.ESCALATE
    assert esc_ctx.state == HarnessState.ESCALATED
    assert esc_ctx.critique_rounds == 2
