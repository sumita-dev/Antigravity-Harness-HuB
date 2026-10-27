---
name: systematic-debugging
description: "Chẩn đoán và sửa lỗi bài bản theo 4 pha cô lập nguyên nhân gốc rễ kết hợp Multi-Hop Agentic RAG."
---
# Systematic Debugging

## Overview

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

> **Ranh giới Hợp đồng & Phân định với Forensics / Why:**
> - `/systematic-debugging`: Quy trình 4 pha kỷ luật để cô lập và xử lý bug chức năng có thể tái hiện được (test failure, logic error, reproducible production bug) nhằm tìm ra nguyên nhân gốc rễ (Root Cause).
> - `/forensics`: Khảo cổ học vết lỗi ngầm đa chặng (Runtime crash, race condition, memory leak, GC thrashing, git bisect regression). Forensics thu thập bằng chứng và chuyển giao nguyên nhân gốc cho `/systematic-debugging`.
> - `/why`: Khảo cổ học quyết định kiến trúc lịch sử (Architecture Decision Rationale & Chesterton's Fence) trước khi sửa hoặc refactor mã nguồn.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Manager wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root Cause Investigation

**BEFORE attempting ANY fix:**

1. **Reproduce Consistently**
   - Create minimal reproduction case
   - Document exact steps/inputs
   - Verify it fails every time
   - If intermittent: identify variables (timing, state, data)

2. **Gather Evidence**
   - Read error messages completely (don't skim)
   - Examine stack traces (note line numbers, call hierarchy)
   - Inspect recent changes (git diff, commits)
   - Check logs, metrics, telemetry
   - Add targeted logging if needed (remove before commit)

3. **Trace Data Flow**
   - Where does bad data originate?
   - Trace backwards from symptom to source
   - Inspect state at each boundary
   - Don't assume values—verify with debugger/logging

4. **Identify Hypothesis**
   - Form testable explanation of WHY it fails
   - "It fails because X causes Y when Z"
   - Must explain ALL observed symptoms
   - If hypothesis doesn't explain everything, keep looking

5. **Test Hypothesis**
   - Make PREDICTION: "If I change X, then Y should happen"
   - Test minimal change to prove/disprove
   - If disproved: return to step 2
   - If proved: proceed to Phase 2

### Phase 2: Pattern Analysis

1. **Find Similar Issues**
   - Has this happened before?
   - Check issue tracker, commit history
   - Look for similar code patterns in codebase
   - Is this systemic or isolated?

2. **Understand Context**
   - Why was it written this way originally?
   - What assumptions changed?
   - What constraints existed?
   - What breaks if we change it?

3. **Determine Scope**
   - Is this a single-line bug or architectural flaw?
   - Are other components affected?
   - Does this need a band-aid or refactor?

### Phase 3: Targeted Fix

1. **Write Failing Test First (TDD)**
   - Minimal unit/regression test reproducing issue
   - Verify test FAILS on current code
   - Verify test failure matches original symptom
   - If test passes, test is wrong or bug not understood

2. **Implement Minimal Fix**
   - Surgical change addressing ROOT CAUSE
   - Don't fix multiple things at once
   - Don't refactor unrelated code
   - Preserve existing behavior except bug

3. **Verify Test Passes**
   - Run the new test: MUST PASS
   - Run FULL test suite: NO REGRESSIONS
   - Check edge cases

### Phase 4: Verification & Hardening

1. **Verify Original Symptom Resolved**
   - Run original reproduction steps
   - Verify bug is truly gone in real environment

2. **Defensive Improvements**
   - Add assertions/type checks if appropriate
   - Improve error messages for future debuggers
   - Update documentation if assumptions changed
   - Use `anti-hallucination-guard` before claiming success
