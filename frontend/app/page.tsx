"use client";

import { useRef, useState } from "react";
import { formatVND, streamSearch, type ProgressEvent, type SearchResult } from "../lib/api";

const STEPS = ["planner", "flight_search", "summarizer"] as const;

export default function Home() {
  const [origin, setOrigin] = useState("SGN");
  const [destination, setDestination] = useState("HAN");
  const [date, setDate] = useState("2026-09-21");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setProgress([]);
    setResult(null);
    setError(null);
    try {
      const r = await streamSearch(
        { origin, destination, date },
        (ev) => setProgress((p) => [...p, ev]),
        ctrl.signal,
      );
      setResult(r);
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <header className="rounded-xl bg-amber-950 px-6 py-5 text-amber-50">
        <h1 className="text-xl font-bold">Tìm vé máy bay bằng AI Agent</h1>
        <p className="mt-1 text-sm text-amber-200">
          Multi-agent: lập kế hoạch, tìm trên Kayak, tóm tắt 3 lựa chọn tốt nhất
        </p>
      </header>

      <form onSubmit={onSearch} className="mt-5 rounded-xl bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Điểm đi</span>
            <input
              value={origin}
              onChange={(e) => setOrigin(e.target.value.toUpperCase())}
              maxLength={3}
              placeholder="SGN"
              className="w-full rounded-md border border-stone-300 px-3 py-2 uppercase"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Điểm đến</span>
            <input
              value={destination}
              onChange={(e) => setDestination(e.target.value.toUpperCase())}
              maxLength={3}
              placeholder="HAN"
              className="w-full rounded-md border border-stone-300 px-3 py-2 uppercase"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Ngày bay</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-md border border-stone-300 px-3 py-2"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="mt-4 rounded-md bg-amber-800 px-5 py-2 font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Đang tìm..." : "Tìm chuyến bay"}
        </button>
      </form>

      {error && (
        <p className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-800">{error}</p>
      )}

      {(loading || progress.length > 0) && (
        <section className="mt-4 rounded-xl bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold">Tiến độ agent</h2>
          <ol className="mt-2 space-y-1 text-sm">
            {STEPS.map((s) => {
              const hit = progress.find((p) => p.step === s);
              return (
                <li key={s} className={hit ? "text-stone-900" : "text-stone-400"}>
                  {hit ? `✓ ${hit.message} ${hit.order}` : `○ ${s}...`}
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {result && (
        <section className="mt-4 space-y-4">
          <div className="rounded-xl bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="font-semibold">
                {result.origin} → {result.destination} · {result.date}
              </span>
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                nguồn: {result.source === "mock" ? "dữ liệu mock" : result.source}
              </span>
              <span className="text-xs text-stone-500">lấy lúc {result.fetched_at}</span>
            </div>
            <a
              href={result.kayak_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-block text-sm text-sky-700 underline"
            >
              Mở link Kayak để tự kiểm tra giá
            </a>
          </div>

          <div className="overflow-hidden rounded-xl bg-white shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-amber-950 text-left text-amber-50">
                  <th className="px-4 py-2">Lựa chọn</th>
                  <th className="px-4 py-2">Giờ</th>
                  <th className="px-4 py-2">Giá</th>
                  <th className="px-4 py-2">Lý do</th>
                </tr>
              </thead>
              <tbody>
                {result.recommendations.map((r) => (
                  <tr key={r.label} className="border-t border-stone-200">
                    <td className="px-4 py-2 font-semibold">{r.label}</td>
                    <td className="px-4 py-2">
                      {r.flight.departure_time} · {r.flight.airline}
                    </td>
                    <td className="px-4 py-2">{formatVND(r.flight.price_vnd)}</td>
                    <td className="px-4 py-2 text-stone-600">{r.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <details className="rounded-xl bg-white p-5 text-sm shadow-sm">
            <summary className="cursor-pointer font-semibold">
              Xem cả 5 chuyến agent đã đọc
            </summary>
            <ul className="mt-2 space-y-1 text-stone-700">
              {result.flights.map((f, i) => (
                <li key={i}>
                  {f.departure_time} · {f.airline} · {formatVND(f.price_vnd)} · {f.baggage}
                </li>
              ))}
            </ul>
          </details>
        </section>
      )}
    </main>
  );
}
