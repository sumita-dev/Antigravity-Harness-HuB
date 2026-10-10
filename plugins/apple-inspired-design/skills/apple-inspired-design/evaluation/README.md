# Evidence-led Design Evaluation (v4)

## Rubric and evaluation contract

Weights: visualHierarchy=20, layoutSpacing=15, typography=15, colorContrast=10, componentConsistency=15, interactionUX=10, responsive=10, motionPolish=5. See `rubric.json` and `references/design-rubric.md`.

Each review is for exactly one route and viewport. `metrics` is an object keyed by rubric ID. A rated item needs score 0..5, confidence >= 0.55, a written summary and at least one evidence object `{type,ref,observation}`. Types: `screenshot`, `dom`, `test`, `interaction`, `token`, `manual`. An unassessed item has `score:null` and `reason`. Score 0 indicates observed severe failure; missing evidence is **never scored as zero**.

```json
{
  "source": "human-review",
  "technicalGate": "pass",
  "reviews": [{"route":"/dashboard","viewport":"desktop-1440","metrics": {
    "visualHierarchy": {"score":4,"confidence":0.85,"summary":"Main CTA is clearly distinguished.","recommendation":"Minor refinement only.","evidence":[{"type":"screenshot","ref":"capture/example.png","observation":"Primary CTA in top-right dominates secondary buttons."}]},
    "motionPolish": {"score":null,"reason":"No motion sample was collected."}
  }}]
}
```

Other metrics can be omitted (reported unassessed). `technicalGate` must be one of `pass`, `fail`, `unverified`; `pass` should be based on actual QA, not a model guess.

```bash
node evaluation/scoring-engine.mjs --input review.json --out artifacts/design-quality
node evaluation/scoring-engine.mjs --input review.json --out artifacts/design-quality --strict
```

Generated files: `score.json`, `issues.json`, `report.md`. `--strict` exits code 2 if score is not trustworthy; trustworthiness requires technical gate pass, average evaluated weight >=75%, and at least one rated item. Passing does **not** mean a good score or design approval. Score is weighted average over **assessed** metrics only; every report shows coverage to prevent misleading comparisons. Compare two scores only with similar coverage and matching routes/states.

## Native Vision SubAgent (`apple-design-critic`) — Luồng mặc định

Trong Antigravity, việc chấm điểm giao diện được thực hiện trực tiếp bởi SubAgent **Apple Design Critic** (`agents/app/apple_design_critic.md` và `agents/design-critic.md`) sử dụng năng lực thị giác đa phương thức native của Gemini:

1. **Thu thập bằng chứng:** Chạy `cd qa && npm run qa:design:capture` để chụp ảnh màn hình các viewports (`mobile-390.png`, `tablet-768.png`, `desktop-1440.png`) và trích xuất `capture.json`.
2. **Kiểm tra trực quan native:** SubAgent dùng công cụ `view_file` mở xem trực tiếp từng ảnh PNG, đọc metadata DOM từ `capture.json` và kết quả test từ `qa/artifacts/visual-qa/audit.json`.
3. **Chấm điểm theo Rubric:** Đánh giá 8 tiêu chí theo `rubric.json` và `references/design-rubric.md` (thang 0-5, confidence >= 0.55). Tiêu chí thiếu bằng chứng gán `score: null` kèm `reason`, không gán 0.
4. **Xuất review:** SubAgent ghi file `qa/artifacts/design-quality/review.json`.
5. **Chạy Scoring Engine:** Chạy `node evaluation/scoring-engine.mjs --input qa/artifacts/design-quality/review.json --out qa/artifacts/design-quality` để xuất `score.json`, `issues.json` và `report.md`.

> **Ưu điểm cốt lõi:** Hoàn toàn **native** bên trong Antigravity, **100% KHÔNG CẦN `GEMINI_API_KEY`**, bảo mật dữ liệu cục bộ tuyệt đối (không gửi hình ảnh ra dịch vụ ngoài).

## CLI Fallback: External Gemini Vision API (`critic-gemini.mjs`) — Tùy chọn cho CI/CD ngoài

Dành cho môi trường CI/CD headless hoặc bên ngoài Antigravity không có native subagent:

1. Chạy `cd qa && npm run qa:design:capture`. Nó tạo ra hình ảnh và metadata.
2. Rà soát ảnh chụp để tránh lộ bí mật, dữ liệu cá nhân trước khi gửi lên API bên ngoài.
3. Cấu hình biến môi trường: `GEMINI_API_KEY`, `UI_CRITIC_MODEL` (`gemini-2.5-flash` hoặc `gemini-2.5-pro`), `UI_ALLOW_EXTERNAL_IMAGES=1`.
4. Chạy lệnh:
   ```bash
   node evaluation/critic-gemini.mjs --capture qa/artifacts/design-capture/capture.json \
     --technical-audit qa/artifacts/visual-qa/audit.json \
     --out qa/artifacts/design-quality/ai-review.json
   ```
5. Chạy scoring engine trên file kết quả:
   ```bash
   node evaluation/scoring-engine.mjs --input qa/artifacts/design-quality/ai-review.json --out qa/artifacts/design-quality
   ```

Script này gửi từng ảnh PNG và DOM metadata lên Google Gemini Vision API bên ngoài, yêu cầu API key và chỉ dùng khi có sự cho phép rõ ràng. Không chạy mặc định trong Antigravity.

## Model-agnostic option

Bất kỳ AI agent nào (Claude, Codex, Antigravity native v.v.) đều có thể tạo ra cùng định dạng JSON review bằng cách mở xem các ảnh chụp màn hình và rubric. Chuyển output qua local scoring engine `evaluation/scoring-engine.mjs`. Điều này giúp quy trình chấm điểm không bị phụ thuộc vào một nhà cung cấp cụ thể. Không bao giờ chỉ đạo AI bịa đặt điểm số hoặc bằng chứng tương tác không có thật.

### Responsive comparison mode

Theo mặc định, mỗi route/viewport được chấm độc lập. Khi đánh giá tiêu chí `responsive`, cần so sánh trực quan tối thiểu hai ảnh chụp viewport khác nhau của cùng một route (ví dụ `mobile-390.png` và `desktop-1440.png`). Nếu chỉ có một viewport duy nhất, bắt buộc ghi nhận `responsive` là `score: null` kèm lý do.
