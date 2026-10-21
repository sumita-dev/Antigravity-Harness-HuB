---
name: youtube-suggest
description: "Thu thập từ khóa gợi ý tự động (Autocomplete / Search Suggestions) trên YouTube theo từ khóa gốc, hỗ trợ mở rộng A-Z (Alphabet Soup), câu hỏi (Modifiers), đào sâu đệ quy và xuất file CSV/JSON."
---

# YouTube Suggest Skill

Skill này cung cấp công cụ tự động cào và mở rộng bộ từ khóa tìm kiếm thực tế trên YouTube (YouTube Autocomplete / Search Suggestions API) nhằm phục vụ nghiên cứu thị trường, lập dàn ý nội dung (Content Plan), tối ưu SEO YouTube và phát hiện xu hướng tìm kiếm ngách (Long-tail keywords).

## 1. Khi Nào Kích Hoạt Skill Này
- Khi người dùng yêu cầu: *"tìm từ khóa youtube về..."*, *"nghiên cứu keyword youtube cho chủ đề X"*, *"gợi ý video youtube theo từ khóa Y"*, *"chạy youtube suggest cho Z"*.
- Khi cần xây dựng cụm chủ đề (topic cluster) hoặc lập danh sách tiêu đề video cho kênh YouTube.
- Khi cần phân tích xu hướng câu hỏi của khán giả (cách, hướng dẫn, là gì, lừa đảo, kinh nghiệm...).

---

## 2. Kiến Trúc & Các Chế Độ Thu Thập (Modes)

Script lõi nằm tại:
`plugins/marketing/skills/youtube-suggest/scripts/fetch_suggestions.py`
*(sau khi cài global: `~/.gemini/config/plugins/marketing/skills/youtube-suggest/scripts/fetch_suggestions.py`)*

### Bốn Chế Độ Thu Thập:
1. **`basic` (Mặc định - Nhanh):**
   - Chỉ truy vấn trực tiếp từ khóa gốc (Seed).
   - Trả về ~10-15 từ khóa gợi ý phổ biến nhất của YouTube.
   - Thời gian thực thi: < 1 giây.
2. **`alphabet` (Alphabet Soup: A-Z & 0-9):**
   - Mở rộng mẫu: `{seed} a`, `{seed} b`, ..., `{seed} z`, `{seed} 0` .. `9`.
   - Giúp tìm ra mọi biến thể đuôi dài của từ khóa theo thứ tự bảng chữ cái.
   - Thu thập: 150 - 300+ từ khóa độc nhất.
3. **`modifiers` (Câu hỏi & Ý định tìm kiếm):**
   - Ghép các tiền tố/hậu tố phổ biến bằng tiếng Việt (`cách`, `hướng dẫn`, `kinh nghiệm`, `review`, `là gì`, `lừa đảo`, `cho người mới`, `ở đâu`...) hoặc tiếng Anh (`how to`, `tutorial`, `best`, `for beginners`...).
   - Rất hữu hiệu để lập ý tưởng kịch bản video trả lời thắc mắc của người xem.
4. **`deep` (Kết hợp toàn diện + Đào sâu 2 tầng):**
   - Kết hợp `basic` + `alphabet` + `modifiers`.
   - Chọn lọc thêm top 3 từ khóa tiềm năng phát hiện được để đệ quy đào sâu thêm 1 tầng.
   - Thích hợp khi muốn lập toàn bộ cơ sở dữ liệu từ khóa cho một kênh ngách.

---

## 3. Cú Pháp Dòng Lệnh (CLI Usage)

```powershell
python plugins/marketing/skills/youtube-suggest/scripts/fetch_suggestions.py [OPTIONS]
```

### Các Tham Số CLI:
| Tham số | Viết tắt | Mặc định | Mô tả |
| :--- | :--- | :--- | :--- |
| `--keyword` | `-k` | *(Bắt buộc)* | Từ khóa hạt giống (Seed keyword) |
| `--mode` | `-m` | `basic` | Chế độ: `basic`, `alphabet`, `modifiers`, `deep` |
| `--lang` | `-l` | `vi` | Mã ngôn ngữ hiển thị (vd: `vi`, `en`, `ja`) |
| `--geo` | `-g` | `vn` | Mã quốc gia/vùng lãnh thổ (vd: `vn`, `us`) |
| `--output` | `-o` | `None` | Đường dẫn file xuất kết quả (.csv hoặc .json) |
| `--format` | `-f` | Tự nhận diện | Định dạng file xuất: `csv` hoặc `json` |
| `--delay-min`| | `0.1` | Thời gian trễ ngẫu nhiên tối thiểu (giây) |
| `--delay-max`| | `0.25`| Thời gian trễ ngẫu nhiên tối đa (giây) |

---

## 4. Các Ví Dụ Thực Tế

### Ví dụ 1: Lấy gợi ý nhanh cho từ khóa "forex" (Basic)
```powershell
python plugins/marketing/skills/youtube-suggest/scripts/fetch_suggestions.py -k "forex" -m basic
```

### Ví dụ 2: Lấy các câu hỏi / thắc mắc của người dùng về "chứng khoán" xuất ra CSV
```powershell
python plugins/marketing/skills/youtube-suggest/scripts/fetch_suggestions.py -k "chứng khoán" -m modifiers -o "chung_khoan_modifiers.csv"
```
*(File CSV được mã hóa UTF-8 BOM, mở trực tiếp bằng Microsoft Excel không bị lỗi font tiếng Việt).*

### Ví dụ 3: Quét cạn kiệt từ khóa A-Z cho "tiếng anh giao tiếp" xuất ra JSON
```powershell
python plugins/marketing/skills/youtube-suggest/scripts/fetch_suggestions.py -k "tiếng anh giao tiếp" -m alphabet -o "tieng_anh_alphabet.json"
```

### Ví dụ 4: Nghiên cứu thị trường Mỹ (English) cho chủ đề "affiliate marketing"
```powershell
python plugins/marketing/skills/youtube-suggest/scripts/fetch_suggestions.py -k "affiliate marketing" -m modifiers -l "en" -g "us" -o "affiliate_us.csv"
```

---

## 5. Cấu Trúc Dữ Liệu Xuất Ra

### 1. Định Dạng CSV
Cột tiêu đề: `rank,keyword,seed,mode,source_query,pattern`
- `rank`: Thứ tự phát hiện và độ ưu tiên gợi ý.
- `keyword`: Từ khóa gợi ý đầy đủ nhận được từ YouTube.
- `seed`: Từ khóa gốc ban đầu.
- `mode`: Chế độ cào dữ liệu (`basic`, `alphabet`, `modifiers`, `deep`).
- `source_query`: Chuỗi truy vấn gửi lên YouTube API để kích hoạt gợi ý này.
- `pattern`: Nhãn nhận diện pattern (ví dụ: `seed`, `alphabet: a`, `prefix: cách`, `suffix: là gì`).

### 2. Định Dạng JSON
```json
{
  "seed": "forex",
  "mode": "basic",
  "lang": "vi",
  "geo": "vn",
  "total": 10,
  "generated_at": "2026-10-21 22:33:00",
  "suggestions": [
    {
      "rank": 1,
      "keyword": "forex",
      "source_query": "forex",
      "pattern": "seed"
    },
    {
      "rank": 2,
      "keyword": "forex là gì",
      "source_query": "forex",
      "pattern": "seed"
    }
  ]
}
```

---

## 6. Kiểm Thử & Bảo Trì

Bộ test E2E kiểm chứng logic thu thập, tính toàn vẹn ký tự Unicode/tiếng Việt và xuất file nằm tại:
```powershell
python plugins/marketing/skills/youtube-suggest/tests/test_e2e.py
```
Kết quả mong đợi: `Ran 3 tests in ... OK`.
