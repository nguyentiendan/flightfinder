"use client";

import { useRef, useState } from "react";
import {
  formatVND,
  priceSourceBadge,
  streamSearch,
  type ProgressEvent,
  type SearchResult,
} from "../lib/api";

const KNOWN_STEPS = ["intake", "planner", "scout_amadeus", "merger", "recommender"] as const;

const STEP_LABELS: Record<(typeof KNOWN_STEPS)[number], string> = {
  intake: "Reading your request...",
  planner: "Choosing fare sources...",
  scout_amadeus: "Querying Amadeus...",
  merger: "Merging fares...",
  recommender: "Picking Cheapest, Balanced, and Flexible...",
};

type ProgressRow = { key: string; hit?: ProgressEvent; fallback: string };

function progressRows(progress: ProgressEvent[]): ProgressRow[] {
  const known = new Set<string>(KNOWN_STEPS);
  const extras = progress.filter((event) => !known.has(event.step));
  const rows: ProgressRow[] = [];
  for (const step of KNOWN_STEPS) {
    if (step === "scout_amadeus") {
      extras.forEach((event, index) => {
        rows.push({
          key: `${event.step}-${index}`,
          hit: event,
          fallback: event.message || event.step,
        });
      });
    }
    rows.push({
      key: step,
      hit: progress.find((event) => event.step === step),
      fallback: STEP_LABELS[step],
    });
  }
  return rows;
}

export default function Home() {
  const [origin, setOrigin] = useState("SGN");
  const [destination, setDestination] = useState("HAN");
  const [date, setDate] = useState("2026-09-21");
  const [message, setMessage] = useState("");
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
        { origin, destination, date, message },
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

  const asking = (result?.need_slots.length ?? 0) > 0;
  const badge = result ? priceSourceBadge(result.price_source) : null;
  const showRoute = Boolean(result && (result.origin || result.destination || result.date));

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <header className="rounded-xl bg-amber-950 px-6 py-5 text-amber-50">
        <h1 className="text-xl font-bold">AI Flight Finder</h1>
        <p className="mt-1 text-sm text-amber-200">
          A multi-agent search that ranks cheap fares first and compares OTA links.
        </p>
      </header>

      <form onSubmit={onSearch} className="mt-5 rounded-xl bg-white p-5 shadow-sm">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Origin</span>
            <input
              value={origin}
              onChange={(e) => setOrigin(e.target.value.toUpperCase())}
              maxLength={3}
              placeholder="SGN"
              className="w-full rounded-md border border-stone-300 px-3 py-2 uppercase"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Destination</span>
            <input
              value={destination}
              onChange={(e) => setDestination(e.target.value.toUpperCase())}
              maxLength={3}
              placeholder="HAN"
              className="w-full rounded-md border border-stone-300 px-3 py-2 uppercase"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Date</span>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-md border border-stone-300 px-3 py-2"
            />
          </label>
        </div>
        <label className="mt-4 block">
          <span className="mb-1 block text-sm font-medium">Ask the agent</span>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            className="w-full rounded-md border border-stone-300 px-3 py-2"
          />
        </label>
        <button
          type="submit"
          disabled={loading}
          className="mt-4 rounded-md bg-amber-800 px-5 py-2 font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Searching..." : "Search flights"}
        </button>
      </form>

      {error && (
        <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{error}</p>
      )}

      {(loading || progress.length > 0) && (
        <section className="mt-4 rounded-xl bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold">Agent progress</h2>
          <ol className="mt-2 space-y-1 text-sm">
            {progressRows(progress).map((row) => (
              <li key={row.key} className={row.hit ? "text-stone-900" : "text-stone-400"}>
                {row.hit ? `✓ ${row.hit.message} ${row.hit.order}` : `○ ${row.fallback}`}
              </li>
            ))}
          </ol>
        </section>
      )}

      {result && (
        <section className="mt-4 space-y-4">
          <div className="rounded-xl bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              {showRoute && (
                <span className="font-semibold">
                  {result.origin} → {result.destination} · {result.date}
                </span>
              )}
              {badge && (
                <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
                  {badge}
                </span>
              )}
              {result.fetched_at && (
                <span className="text-xs text-stone-500">fetched at {result.fetched_at}</span>
              )}
            </div>
            {result.ota_links.some((link) => link.search_url) && (
              <ul className="mt-2 space-y-1">
                {result.ota_links.filter((link) => link.search_url).map((link) => (
                  <li key={link.source_id}>
                    <a
                      href={link.search_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm text-sky-700 underline"
                    >
                      Compare on {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {asking && (
            <p className="rounded-xl bg-white px-5 py-4 text-sm shadow-sm">{result.intake_question}</p>
          )}

          {result.errors.length > 0 && (
            <ul className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {result.errors.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          )}

          {!asking && result.recommendations.length > 0 && (
            <div className="overflow-hidden rounded-xl bg-white shadow-sm">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-amber-950 text-left text-amber-50">
                    <th className="px-4 py-2">Choice</th>
                    <th className="px-4 py-2">Time</th>
                    <th className="px-4 py-2">Price</th>
                    <th className="px-4 py-2">Why</th>
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
          )}

          {!asking && result.flights.length > 0 && (
            <details className="rounded-xl bg-white p-5 text-sm shadow-sm">
              <summary className="cursor-pointer font-semibold">All offers the agents read</summary>
              <ul className="mt-2 space-y-1 text-stone-700">
                {result.flights.map((f, i) => (
                  <li key={`${f.airline}-${f.departure_time}-${i}`}>
                    {f.departure_time} · {f.airline} · {formatVND(f.price_vnd)} · {f.baggage}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}
    </main>
  );
}
