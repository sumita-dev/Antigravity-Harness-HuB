---
name: ponytail-review
description: "Code review chống over-engineering - rà soát và loại bỏ abstraction/mã phình dư thừa."
---
Review diffs for unnecessary complexity. One line per finding: location, what
to cut, what replaces it. The diff's best outcome is getting shorter.

> **Ranh giới Hợp đồng & Phân định với Karpathy Coder:**
> - `/ponytail-review` chuyên trách: Rà soát đối kháng sau khi viết mã (Diff Review, tìm và cắt bỏ abstraction thừa, dead code, single-impl interfaces). Hỗ trợ script phân tích tĩnh tất định `scripts/lint_overengineering.py`.
> - `/karpathy-coder` chuyên trách: Tư duy & kỷ luật thực thi trong lúc viết mã (Think Before Coding, Simplicity First, Surgical Changes).

## Format

`L<line>: <tag> <what>. <replacement>.`, or `<file>:L<line>: ...` for
multi-file diffs.

Tags:

- `delete:` dead code, unused flexibility, speculative feature. Replacement: nothing.
- `stdlib:` hand-rolled thing the standard library ships. Name the function.
- `native:` dependency or code doing what the platform already does. Name the feature.
- `yagni:` abstraction with one implementation, config nobody sets, layer with one caller.
- `shrink:` same logic, fewer lines. Show the shorter form.

## Examples

❌ "This EmailValidator class might be more complex than necessary, have you
considered whether all these validation rules are needed at this stage?"

✅ `L12-38: stdlib: 27-line validator class. "@" in email, 1 line, real validation is the confirmation mail.`

✅ `L4: native: moment.js imported for one format call. Intl.DateTimeFormat, 0 deps.`

✅ `repo.py:L88: yagni: AbstractRepository with one implementation. Inline it until a second one exists.`

✅ `L52-71: delete: retry wrapper around an idempotent local call. Nothing replaces it.`

✅ `L30-44: shrink: manual loop builds dict. dict(zip(keys, values)), 1 line.`

## Scoring

End with the only metric that matters: `net: -<N> lines possible.`

If there is nothing to cut, say `Lean already. Ship.` and stop.

## Chống Thiên Kiến Phức Tạp (Anti-Complexity Bias)

Giữ nguyên codebase tối giản ban đầu là kết quả hoàn toàn hợp lệ và đáng kỳ vọng. Cấm cộng điểm cho các giải pháp cố tình tạo thêm abstraction/lớp thừa (wrappers, speculative interfaces, single-use helpers). Nếu một chức năng có thể giải quyết mà không cần thêm tầng trung gian, giữ nguyên sự tinh gọn ban đầu là phương án chiến thắng.

Hỗ trợ script kiểm tra tĩnh tất định:
```bash
python plugins/code/skills/ponytail-review/scripts/lint_overengineering.py --path <thư_mục_hoặc_file>
```

## Boundaries

Scope: over-engineering and complexity only. Correctness bugs, security holes,
and performance are explicitly out of scope. Route them to a normal review
pass, not this one. A single smoke test or `assert`-based
self-check is the ponytail minimum, not bloat, never flag it for deletion.
Does not apply the fixes, only lists them.
"stop ponytail-review" or "normal mode": revert to verbose review style.
