#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_evidence_cache.py

Bộ kiểm thử 2 tầng cho Pha 3: Evidence-as-Files & Fingerprinting Cache.
Toàn bộ thao tác ghi file sử dụng `tmp_path` để không làm rác repo thật.
"""

import concurrent.futures
import dataclasses
import sys
from enum import Enum
from pathlib import Path

import pytest

from harness.evidence_cache import (
    EvaluationCache,
    EvidenceTreeBuilder,
    call_fingerprint,
    compute_deliverables_digest,
    sanitize_filename,
)
from harness.orchestrator import ChiefOrchestrator
from harness.propose_probe_compose import (
    ProposalVariant,
    ProposeProbeComposeEngine,
    TaskScenario,
)
from harness.quality_gate import AdversarialQualityGate, Verdict
from harness.runners.app_runner import AppRunner
from harness.runners.marketing_runner import MarketingRunner
from harness.state_machine import HarnessState, TaskContext


class _SampleEnum(Enum):
    ALPHA = "alpha"
    BETA = "beta"


@dataclasses.dataclass
class _SampleDataclass:
    name: str
    count: int


class _CustomObject:
    def __init__(self, tag: str):
        self.tag = tag

    def __repr__(self) -> str:
        return f"_CustomObject(tag={self.tag!r})"


# ==============================================================================
# TẦNG 1: UNIT TESTS
# ==============================================================================

def test_evidence_tree_builder_below_and_above_threshold(tmp_path: Path):
    builder = EvidenceTreeBuilder(threshold_chars=100, base_dir=tmp_path)
    assert builder.should_spill("ngắn", "vừa") is False
    long_text = "Nội dung tiếng Việt UTF-8 đầy đủ — " * 20
    assert builder.should_spill(long_text) is True

    tree = builder.build(
        task_id="task_vn_01",
        task_prompt="Kiểm thử UTF-8 và không cắt xén chuỗi",
        deliverables={
            "report": long_text,
            "metrics": {"score": 0.95, "note": "Đạt chuẩn"},
        },
        stage="CRITIC",
        mission_instructions="Đọc deliverables/report.md để kiểm tra.",
    )

    assert tree.task_file.is_file()
    assert tree.index_file.is_file()
    assert tree.mission_file.is_file()
    assert tree.deliverables_dir.is_dir()

    report_file = tree.deliverables_dir / "report.md"
    assert report_file.is_file()
    assert report_file.read_text(encoding="utf-8") == long_text
    assert "Đạt chuẩn" in (tree.deliverables_dir / "metrics.json").read_text(encoding="utf-8")
    assert tree.deliverables_digest in tree.index_file.read_text(encoding="utf-8")

    paths = tree.to_evidence_paths()
    assert str(tree.index_file) in paths
    assert str(tree.mission_file) in paths
    assert str(report_file) in paths


def test_evidence_tree_sanitize_windows_filenames_and_cleanup(tmp_path: Path):
    assert sanitize_filename('bad<>:"/\\|?*name.txt') == "bad_________name.txt"
    assert sanitize_filename("CON") == "CON_file"
    assert sanitize_filename("aux.log") == "aux_file.log"

    builder = EvidenceTreeBuilder(threshold_chars=10, base_dir=None)
    custom_tmp = tmp_path / "auto_ev"
    tree = builder.build(
        task_id="t_clean",
        task_prompt="cleanup test",
        deliverables={'weird:name*?.txt': "full body"},
        dest_dir=custom_tmp,
    )
    assert (tree.deliverables_dir / "weird_name__.txt").is_file()
    # Khi auto_created_tmp=False, cleanup không xóa dest_dir của caller
    tree.cleanup()
    assert custom_tmp.exists()

    # Khi auto_created_tmp=True, cleanup xóa sạch
    tree.auto_created_tmp = True
    tree.cleanup()
    assert not custom_tmp.exists()


def test_call_fingerprint_determinism_and_invalidation():
    d1 = compute_deliverables_digest({"content": "hello", "path": Path("a/b.py")})
    fp_base = call_fingerprint(
        stage="APP_QUALITY_GATE",
        task_prompt="build api",
        deliverables_digest=d1,
        rubrics=[{"name": "clarity", "weight": 1.0}],
        extra={
            "threshold": 0.8,
            "task_tier": "tier_1",
            "planned_steps": ["DESIGN", "IMPLEMENTATION"],
            "actual_steps": ["DESIGN", "IMPLEMENTATION"],
            "compliance_report": {"ok": True},
            "base_variant": "v0",
            "keep_base_margin": 0.02,
            "mode": "contrastive",
        },
    )
    fp_same = call_fingerprint(
        stage="APP_QUALITY_GATE",
        task_prompt="build api",
        deliverables_digest=d1,
        rubrics=[{"weight": 1.0, "name": "clarity"}],
        extra={
            "mode": "contrastive",
            "keep_base_margin": 0.02,
            "base_variant": "v0",
            "compliance_report": {"ok": True},
            "actual_steps": ["DESIGN", "IMPLEMENTATION"],
            "planned_steps": ["DESIGN", "IMPLEMENTATION"],
            "task_tier": "tier_1",
            "threshold": 0.8,
        },
    )
    assert fp_base == fp_same

    mutations = [
        ("deliverables", compute_deliverables_digest({"content": "hello!", "path": Path("a/b.py")}), None, {}),
        ("rubrics", d1, [{"name": "clarity", "weight": 0.9}], {}),
        ("threshold", d1, [{"name": "clarity", "weight": 1.0}], {"threshold": 0.85}),
        ("task_tier", d1, [{"name": "clarity", "weight": 1.0}], {"task_tier": "tier_2"}),
        ("planned_steps", d1, [{"name": "clarity", "weight": 1.0}], {"planned_steps": ["DESIGN"]}),
        ("actual_steps", d1, [{"name": "clarity", "weight": 1.0}], {"actual_steps": ["DESIGN", "CRITIQUE"]}),
        ("compliance_report", d1, [{"name": "clarity", "weight": 1.0}], {"compliance_report": {"ok": False}}),
        ("base_variant", d1, [{"name": "clarity", "weight": 1.0}], {"base_variant": "v1"}),
        ("keep_base_margin", d1, [{"name": "clarity", "weight": 1.0}], {"keep_base_margin": 0.05}),
        ("mode", d1, [{"name": "clarity", "weight": 1.0}], {"mode": "orthogonal"}),
    ]
    base_extra = {
        "threshold": 0.8,
        "task_tier": "tier_1",
        "planned_steps": ["DESIGN", "IMPLEMENTATION"],
        "actual_steps": ["DESIGN", "IMPLEMENTATION"],
        "compliance_report": {"ok": True},
        "base_variant": "v0",
        "keep_base_margin": 0.02,
        "mode": "contrastive",
    }
    for label, dig, rub, patch in mutations:
        merged = {**base_extra, **patch}
        fp_mut = call_fingerprint(
            stage="APP_QUALITY_GATE",
            task_prompt="build api",
            deliverables_digest=dig,
            rubrics=rub if rub is not None else [{"name": "clarity", "weight": 1.0}],
            extra=merged,
        )
        assert fp_mut != fp_base, f"Fingerprint did not change on {label}"


def test_compute_deliverables_digest_non_json_and_large_files(tmp_path: Path):
    # Non-JSON types: Path nested, dataclass, Enum, custom object
    payload = {
        "dc": _SampleDataclass(name="x", count=3),
        "enum": _SampleEnum.ALPHA,
        "path": tmp_path / "sub" / "file.txt",
        "obj": _CustomObject("custom"),
    }
    dig1 = compute_deliverables_digest(payload)
    dig2 = compute_deliverables_digest(payload)
    assert dig1 == dig2 and len(dig1) == 64

    # Directory digest ignores __pycache__ and streams large files with max_file_bytes
    work_dir = tmp_path / "proj"
    work_dir.mkdir()
    (work_dir / "__pycache__").mkdir()
    (work_dir / "__pycache__" / "junk.pyc").write_bytes(b"123456")
    big_file = work_dir / "big.bin"
    big_file.write_bytes(b"A" * 2048)

    d_dir_1 = compute_deliverables_digest(work_dir, max_file_bytes=512)
    # Thay đổi __pycache__ không làm đổi digest
    (work_dir / "__pycache__" / "junk.pyc").write_bytes(b"9999999")
    d_dir_2 = compute_deliverables_digest(work_dir, max_file_bytes=512)
    assert d_dir_1 == d_dir_2

    # Thay đổi kích thước file vượt max_file_bytes -> metadata (size) đổi -> digest đổi
    big_file.write_bytes(b"A" * 4096)
    d_dir_3 = compute_deliverables_digest(work_dir, max_file_bytes=512)
    assert d_dir_3 != d_dir_1


def test_evaluation_cache_memory_and_disk_thread_safety(tmp_path: Path):
    cache_dir = tmp_path / "eval_cache"
    cache = EvaluationCache(cache_dir=cache_dir)

    assert cache.get("missing_fp") is None
    original = {"score": 0.9, "nested": {"ok": True}}
    cache.put("fp_1", original, stage="APP")
    # Sửa dict gốc sau put không làm hỏng cache
    original["nested"]["ok"] = False

    got1 = cache.get("fp_1")
    assert got1 == {"score": 0.9, "nested": {"ok": True}}
    # Sửa dict trả về từ get không làm hỏng cache
    got1["nested"]["ok"] = False
    assert cache.get("fp_1")["nested"]["ok"] is True

    # Reload từ đĩa ở instance mới
    cache_reloaded = EvaluationCache(cache_dir=cache_dir)
    assert cache_reloaded.get("fp_1") == {"score": 0.9, "nested": {"ok": True}}

    stats = cache.stats()
    assert stats["puts"] == 1
    assert stats["hits"] == 2
    assert stats["misses"] == 1

    # Invalidate
    assert cache.invalidate("fp_1") is True
    assert cache.get("fp_1") is None

    # Thread safety
    def _worker(idx: int) -> None:
        key = f"fp_thread_{idx % 5}"
        cache.put(key, {"idx": idx}, stage="THREAD")
        val = cache.get(key)
        assert val is not None and "idx" in val

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(_worker, range(30)))
    assert cache.stats()["entries"] == 5


# ==============================================================================
# TẦNG 2: RUNTIME / INTEGRATION VERIFICATION
# ==============================================================================

def test_quality_gate_cache_hit_miss_and_state_machine(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path / "qg_cache")
    builder = EvidenceTreeBuilder(threshold_chars=200, base_dir=tmp_path / "qg_ev")
    gate = AdversarialQualityGate(cache=cache, evidence_builder=builder)

    # 1. evaluate_app_quality_gate: miss -> hit (vẫn chạy record_step + transition) -> invalidation
    ctx1 = TaskContext(task_id="app_1", branch="app")
    ctx1.transition(HarnessState.INTAKE)
    ctx1.transition(HarnessState.DESIGN)
    ctx1.transition(HarnessState.IMPLEMENTATION)
    ctx1.transition(HarnessState.AUDIT)
    ctx1.record_step("DESIGN", {"ok": True})
    ctx1.record_step("IMPLEMENTATION", {"ok": True})

    v1, d1 = gate.evaluate_app_quality_gate(
        ctx1,
        response_text="Implemented clean REST endpoint with unit tests passing.",
        planned_steps=["DESIGN", "IMPLEMENTATION"],
        threshold=0.5,
    )
    assert v1 == Verdict.APPROVE
    assert ctx1.state == HarnessState.APPROVED
    assert not d1.get("cached")

    ctx2 = TaskContext(task_id="app_2", branch="app")
    ctx2.transition(HarnessState.INTAKE)
    ctx2.transition(HarnessState.DESIGN)
    ctx2.transition(HarnessState.IMPLEMENTATION)
    ctx2.transition(HarnessState.AUDIT)
    ctx2.record_step("DESIGN", {"ok": True})
    ctx2.record_step("IMPLEMENTATION", {"ok": True})

    v2, d2 = gate.evaluate_app_quality_gate(
        ctx2,
        response_text="Implemented clean REST endpoint with unit tests passing.",
        planned_steps=["DESIGN", "IMPLEMENTATION"],
        threshold=0.5,
    )
    assert v2 == Verdict.APPROVE
    assert d2.get("cached") is True
    assert ctx2.state == HarnessState.APPROVED
    assert any(s["step"] == "APP_QUALITY_GATE" and s["payload"].get("cached") is True for s in ctx2.trace_steps)

    # Đổi executed_steps -> phải cache miss
    ctx3 = TaskContext(task_id="app_3", branch="app")
    ctx3.transition(HarnessState.INTAKE)
    ctx3.transition(HarnessState.DESIGN)
    ctx3.transition(HarnessState.IMPLEMENTATION)
    ctx3.transition(HarnessState.AUDIT)
    ctx3.record_step("DESIGN", {"ok": True})
    v3, d3 = gate.evaluate_app_quality_gate(
        ctx3,
        response_text="Implemented clean REST endpoint with unit tests passing.",
        planned_steps=["DESIGN", "IMPLEMENTATION"],
        threshold=0.5,
    )
    assert not d3.get("cached")

    # 2. evaluate_marketing_quality_gate
    m1 = TaskContext(task_id="mkt_1", branch="marketing")
    m1.transition(HarnessState.INTAKE)
    m1.transition(HarnessState.DESIGN)
    m1.transition(HarnessState.IMPLEMENTATION)
    m1.transition(HarnessState.AUDIT)
    mv1, md1 = gate.evaluate_marketing_quality_gate(m1, "Bài viết phân tích chuyên sâu có dẫn chứng.", threshold=0.3)
    assert not md1.get("cached")

    m2 = TaskContext(task_id="mkt_2", branch="marketing")
    m2.transition(HarnessState.INTAKE)
    m2.transition(HarnessState.DESIGN)
    m2.transition(HarnessState.IMPLEMENTATION)
    m2.transition(HarnessState.AUDIT)
    mv2, md2 = gate.evaluate_marketing_quality_gate(m2, "Bài viết phân tích chuyên sâu có dẫn chứng.", threshold=0.3)
    assert md2.get("cached") is True
    assert mv2 == mv1

    # 3. evaluate_quantitative
    q1 = gate.evaluate_quantitative("Clean answer", reference_text="Clean answer")
    q2 = gate.evaluate_quantitative("Clean answer", reference_text="Clean answer")
    q3 = gate.evaluate_quantitative("Clean answer", reference_text="Different reference")
    assert not q1.get("cached")
    assert q2.get("cached") is True
    assert not q3.get("cached")

    # 4. evaluate_execution với stdout > threshold -> giữ preview [:500] và ghi evidence_dir
    exec_ctx = TaskContext(task_id="exec_spill", branch="app")
    exec_ctx.transition(HarnessState.INTAKE)
    exec_ctx.transition(HarnessState.DESIGN)
    exec_ctx.transition(HarnessState.IMPLEMENTATION)
    cmd = f'"{sys.executable}" -c "print(\'A\' * 1200)"'
    ev = gate.evaluate_execution(exec_ctx, cmd)
    assert ev == Verdict.APPROVE
    exec_step = [s for s in exec_ctx.trace_steps if s["step"] == "EXECUTE"][-1]["payload"]
    assert len(exec_step["stdout"]) == 500
    assert "evidence_dir" in exec_step
    stdout_log = Path(exec_step["evidence_dir"]) / "deliverables" / "stdout.log"
    assert stdout_log.is_file()
    assert len(stdout_log.read_text(encoding="utf-8").strip()) == 1200

    # 5. evaluate_critique & evaluate_audit với output > threshold vẫn chuyển trạng thái & tạo EvidenceTree
    c_ctx = TaskContext(task_id="crit_spill", branch="app")
    c_ctx.transition(HarnessState.INTAKE)
    c_ctx.transition(HarnessState.DESIGN)
    c_ctx.transition(HarnessState.IMPLEMENTATION)
    c_ctx.transition(HarnessState.CRITIQUE)
    long_critic = "VERDICT: APPROVE\n" + ("Chi tiết phản biện hợp lệ. " * 30)
    assert gate.evaluate_critique(c_ctx, long_critic, enforce_hallucination_guard=False) == Verdict.APPROVE
    assert c_ctx.state == HarnessState.AUDIT
    critic_step = [s for s in c_ctx.trace_steps if s["step"] == "CRITIC"][-1]["payload"]
    assert "evidence_dir" in critic_step and Path(critic_step["evidence_dir"]).is_dir()


def test_ppc_pipeline_cache_and_invalidation(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path / "ppc_cache")
    engine = ProposeProbeComposeEngine(cache=cache)
    scenario = TaskScenario(
        task_id="ppc_1",
        domain="app",
        title="Rate Limiter",
        description="Build rate limiter",
        required_criteria=["core_functionality", "boundary_guard"],
        blindspot_risk="boundary_guard",
    )
    ctx = TaskContext(task_id="ppc_1", branch="app")
    ctx.task_tier = "tier_1"

    res1 = engine.execute_ppc_pipeline(ctx, prompt="", scenario=scenario, force_tier_1=True)
    assert not res1.get("cached")

    res2 = engine.execute_ppc_pipeline(ctx, prompt="", scenario=scenario, force_tier_1=True)
    assert res2.get("cached") is True
    assert res2["composed"].variant_id == res1["composed"].variant_id

    # Đổi mode -> miss
    res3 = engine.execute_ppc_pipeline(ctx, prompt="", scenario=scenario, force_tier_1=True, mode="orthogonal")
    assert not res3.get("cached")

    # Đổi keep_base_margin với base_variant -> miss
    base_v = ProposalVariant(variant_id="b0", style="baseline", content="base", implemented_features=["core_functionality"])
    res4 = engine.execute_ppc_pipeline(ctx, prompt="", scenario=scenario, force_tier_1=True, base_variant=base_v, keep_base_margin=0.02)
    res5 = engine.execute_ppc_pipeline(ctx, prompt="", scenario=scenario, force_tier_1=True, base_variant=base_v, keep_base_margin=0.25)
    assert not res4.get("cached")
    assert not res5.get("cached")


def test_runners_and_orchestrator_e2e(tmp_path: Path):
    cache = EvaluationCache(cache_dir=tmp_path / "runner_cache")
    builder = EvidenceTreeBuilder(threshold_chars=150, base_dir=tmp_path / "runner_ev")
    gate = AdversarialQualityGate(cache=cache, evidence_builder=builder)

    app_runner = AppRunner(gate)
    ctx_app = TaskContext(task_id="app_e2e", branch="app")
    ctx_app.transition(HarnessState.INTAKE)
    big_spec = "Chi tiết kiến trúc hệ thống " * 20
    v_app = app_runner.run(
        "Build rate limiter",
        ctx_app,
        spec=big_spec,
        enable_ppc=True,
        mock_critic_output="VERDICT: APPROVE",
        mock_checker_output="VERDICT: APPROVE",
    )
    assert v_app == Verdict.APPROVE
    impl_steps = [s for s in ctx_app.trace_steps if s["step"] == "IMPLEMENTATION"]
    assert "evidence_dir" in impl_steps[-1]["payload"]

    mkt_runner = MarketingRunner(gate)
    ctx_mkt = TaskContext(task_id="mkt_e2e", branch="marketing")
    ctx_mkt.transition(HarnessState.INTAKE)
    v_mkt = mkt_runner.run(
        "YouTube storytelling",
        ctx_mkt,
        dossier=big_spec,
        enable_ppc=True,
        mock_critic_output="VERDICT: APPROVE",
        mock_checker_output="VERDICT: APPROVE",
    )
    assert v_mkt == Verdict.APPROVE
    mkt_impl = [s for s in ctx_mkt.trace_steps if s["step"] == "IMPLEMENTATION"]
    assert "evidence_dir" in mkt_impl[-1]["payload"]

    # Orchestrator E2E (redirect trajectory_store sang tmp_path)
    orch = ChiefOrchestrator()
    orch.trajectory_store.path = tmp_path / "trajectories.jsonl"
    orch.evidence_builder.base_dir = tmp_path / "orch_ev"

    o_ctx, o_verdict = orch.process_task("Build rate limiter", branch="app")
    assert o_verdict == Verdict.APPROVE
    trajs = orch.trajectory_store.get_trajectories()
    assert len(trajs) == 1
    assert "cache_stats" in trajs[0]["metadata"]

    fan_results = orch.fan_out_tasks(["Task A", "Task B"], branch="app", max_concurrency=2)
    assert len(fan_results) == 2
    assert all(v == Verdict.APPROVE for _, v in fan_results)
