# Multi-agent Flight Finder

Bám slide **AI_Agents_Cam_nang_minh_hoa_2026_CyberSoft.pdf, trang 72–75**
(Dự án 3 · Multi-Agent · Planning · Cấp độ 4).

Luồng đúng slide: câu hỏi tự nhiên → Kayak Tool tạo URL → Flight Search Agent
lấy top 5 chuyến → Browserbase đọc chi tiết từng chuyến → Summarization Agent
đề xuất 3 lựa chọn (Rẻ nhất / Cân bằng / Linh hoạt).

## Khác slide ở tech stack (đã thống nhất với user)

| Slide | Project này |
|---|---|
| CrewAI | LangGraph (`backend/app/graph.py`: planner → flight_search → summarizer) |
| DeepSeek-R1 qua Ollama | OpenAI `gpt-4o-mini`; **chưa có key thì chạy mock** |
| Streamlit | Next.js + Tailwind (`frontend/`) |
| Browserbase + Playwright cạo Kayak thật | **Mock data** trước (`backend/app/tools/flight_data.py`); thay hàm `search_flights` là cắm scrape thật được |

Điểm giữ nguyên theo slide: 2 task nối tiếp (task sau dùng context task trước),
`planning=True` tương đương (node `planner` viết kế hoạch trước), giới hạn độ
dài text đưa vào LLM, hiển thị **tiến độ từng bước** (SSE), ghi **thời điểm lấy
dữ liệu + link Kayak** để user tự kiểm tra, guardrail chống bịa giá.

## Chạy local

Yêu cầu: `uv`, `node`/`npm`, file `backend/.env` (copy từ `.env.example`;
chưa có `OPENAI_API_KEY` thì chạy mock).

```bash
# Backend (http://localhost:8000, docs: /docs)
cd backend && cp .env.example .env && uv sync --group dev && uv run uvicorn app.main:app --reload

# Frontend (http://localhost:3000) — terminal khác
cd frontend && npm install && npm run dev
```

## Chạy Docker

```bash
cp backend/.env.example backend/.env   # điền OPENAI_API_KEY khi anh gửi key
docker compose up --build
```

Mở trình duyệt tại [http://localhost:3000](http://localhost:3000).

## Cấu trúc

```text
backend/           FastAPI + LangGraph
  app/main.py      REST + SSE tiến độ (GET /api/search/stream)
  app/graph.py     3 node: planner → flight_search → summarizer
  app/tools/       kayak.py (tạo URL) + flight_data.py (mock)
  tests/           pytest, chạy: uv run pytest
frontend/          Next.js + Tailwind (form, tiến độ, bảng 3 lựa chọn)
docker-compose.yml backend:8000 + frontend:3000
```
