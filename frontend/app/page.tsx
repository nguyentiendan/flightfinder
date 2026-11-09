"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  formatUSD,
  lookupPlace,
  priceSourceBadge,
  streamSearch,
  type PlaceAirport,
  type ProgressEvent,
  type SearchResult,
} from "../lib/api";
import {
  choiceQuestion,
  radioLabel,
  unknownPlaceQuestion,
} from "../lib/places";
import {
  displayCity,
  followupText,
  rewriteMessage,
  slotPlaceholder,
} from "../lib/rewriteMessage";

const PLACEHOLDER = "I want to fly from SaiGon to Narita at 2026/11/1";

type SlotMemory = { origin: string; destination: string; date: string };

const EMPTY_SLOTS: SlotMemory = { origin: "", destination: "", date: "" };

export default function Home() {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<ProgressEvent[]>([]);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pendingNeed, setPendingNeed] = useState<string[]>([]);
  const [slotAnswers, setSlotAnswers] = useState<SlotMemory>({ ...EMPTY_SLOTS });
  const [bubbleDraft, setBubbleDraft] = useState("");
  const [airportOptions, setAirportOptions] = useState<PlaceAirport[] | null>(null);
  const [choicePlace, setChoicePlace] = useState("");
  const [pickedCode, setPickedCode] = useState("");
  const [placeMiss, setPlaceMiss] = useState("");
  const [choicesLoading, setChoicesLoading] = useState(false);
  const slotsRef = useRef<SlotMemory>({ ...EMPTY_SLOTS });
  const abortRef = useRef<AbortController | null>(null);
  const bubbleInputRef = useRef<HTMLInputElement>(null);

  const asking = pendingNeed.length > 0;
  const blocked = Boolean(result?.blocked);
  const badge = result ? priceSourceBadge(result.price_source) : null;
  const showRoute = Boolean(result && (result.origin || result.destination || result.date));
  const displaySlots = {
    origin: slotAnswers.origin || displayCity(result?.origin ?? ""),
    destination: slotAnswers.destination || displayCity(result?.destination ?? ""),
    date: slotAnswers.date || (result?.date ?? ""),
  };
  const agentText = blocked
    ? result?.intake_question ?? ""
    : airportOptions
      ? `${followupText(displaySlots, [])}\n\n${choiceQuestion(choicePlace, pendingNeed[0])}`.trim()
      : placeMiss
        ? `${followupText(displaySlots, [])}\n\n${unknownPlaceQuestion(placeMiss)}`.trim()
        : asking
          ? followupText(displaySlots, pendingNeed)
          : result?.intake_question ?? "";

  useEffect(() => {
    if (asking) bubbleInputRef.current?.focus();
  }, [asking, pendingNeed[0]]);

  async function runSearch(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setProgress([]);
    setResult(null);
    setError(null);
    setPendingNeed([]);
    setBubbleDraft("");
    setAirportOptions(null);
    setChoicePlace("");
    setPickedCode("");
    setPlaceMiss("");
    setChoicesLoading(false);
    try {
      const remembered = slotsRef.current;
      const r = await streamSearch(
        {
          origin: remembered.origin,
          destination: remembered.destination,
          date: remembered.date,
          message: trimmed,
        },
        (ev) => setProgress((prev) => [...prev, ev]),
        ctrl.signal,
      );
      setResult(r);
      if (r.blocked) {
        slotsRef.current = { ...EMPTY_SLOTS };
        setSlotAnswers({ ...EMPTY_SLOTS });
        setPendingNeed([]);
      } else if (r.need_slots.length > 0) {
        slotsRef.current = {
          origin: r.origin,
          destination: r.destination,
          date: r.date,
        };
        setSlotAnswers({ ...EMPTY_SLOTS });
        setPendingNeed(r.need_slots);
      } else {
        slotsRef.current = { ...EMPTY_SLOTS };
        setSlotAnswers({ ...EMPTY_SLOTS });
        setPendingNeed([]);
        setMessage("");
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function onSearch(e: FormEvent) {
    e.preventDefault();
    void runSearch(message);
  }

  async function applySlotAnswer(
    slot: string,
    answer: string,
    resolved = false,
    baseMessage = message,
  ) {
    const next = rewriteMessage(baseMessage, slot, answer);
    setMessage(next);
    setBubbleDraft("");
    setPlaceMiss("");
    if ((slot === "origin" || slot === "destination") && !resolved) {
      setChoicesLoading(true);
      try {
        const looked = await lookupPlace(answer);
        if (looked.kind === "ambiguous" && looked.airports.length >= 2) {
          setSlotAnswers((prev) => ({ ...prev, [slot]: answer }));
          setAirportOptions(looked.airports);
          setChoicePlace(answer);
          setPickedCode("");
          return;
        }
        if (looked.kind === "city" && looked.airports.length === 1) {
          await applySlotAnswer(slot, radioLabel(looked.airports[0]), true, next);
          return;
        }
        if (looked.kind === "unknown") {
          setSlotAnswers((prev) => ({ ...prev, [slot]: answer }));
          setAirportOptions(null);
          setPlaceMiss(answer);
          return;
        }
      } catch {
        setSlotAnswers((prev) => ({ ...prev, [slot]: answer }));
        setAirportOptions(null);
        setPlaceMiss(answer);
        return;
      } finally {
        setChoicesLoading(false);
      }
    }
    setAirportOptions(null);
    setChoicePlace("");
    setPickedCode("");
    setSlotAnswers((prev) => ({ ...prev, [slot]: answer }));
    const rest = pendingNeed.slice(1);
    if (rest.length === 0) {
      setPendingNeed([]);
      void runSearch(next);
      return;
    }
    setPendingNeed(rest);
  }

  function onBubbleSubmit() {
    const slot = pendingNeed[0];
    const answer = bubbleDraft.trim();
    if (!slot || !answer || loading || choicesLoading) return;
    void applySlotAnswer(slot, answer);
  }

  function onPickAirport(item: PlaceAirport) {
    const slot = pendingNeed[0];
    if (!slot || loading || choicesLoading) return;
    setPickedCode(item.code);
    void applySlotAnswer(slot, radioLabel(item), true);
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <header className="rounded-xl bg-amber-950 px-6 py-5 text-amber-50">
        <h1 className="text-xl font-bold">AI Flight Finder</h1>
        <p className="mt-1 text-sm text-amber-200">
          A multi-agent search that ranks cheap fares first and compares OTA links.
        </p>
      </header>

      <form onSubmit={onSearch} className="mt-5 rounded-xl bg-white p-5 shadow-sm">
        <label className="block">
          <span className="mb-1 block text-sm font-medium">Ask the agent</span>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            placeholder={PLACEHOLDER}
            className="w-full rounded-md border border-stone-300 px-3 py-2 placeholder:text-stone-400"
          />
        </label>
        <button
          type="submit"
          disabled={loading || !message.trim()}
          className="mt-4 rounded-md bg-amber-800 px-5 py-2 font-semibold text-white disabled:opacity-50"
        >
          {loading ? "Searching..." : "Search flights"}
        </button>
      </form>

      {error && (
        <p className="mt-4 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">{error}</p>
      )}

      {loading && progress.length > 0 && (
        <ul className="mt-4 rounded-xl bg-white px-5 py-4 text-sm text-stone-700 shadow-sm">
          {progress.map((ev, index) => (
            <li key={`${ev.step}-${index}`}>{ev.message}</li>
          ))}
        </ul>
      )}

      {result && (
        <section className="mt-4 space-y-4">
          {(asking || blocked) && agentText && (
            <div className="rounded-xl bg-white px-5 py-4 text-sm shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-stone-500">Agent</p>
              <p className="mt-2 whitespace-pre-line text-stone-800">{agentText}</p>
              {choicesLoading && (
                <p className="mt-2 text-stone-500">Looking up airports...</p>
              )}
              {asking && airportOptions && (
                <fieldset className="mt-3 space-y-2">
                  <legend className="sr-only">Airports</legend>
                  {airportOptions.map((item) => (
                    <label
                      key={item.code}
                      className="flex cursor-pointer items-center gap-2 rounded-md border border-stone-200 px-3 py-2"
                    >
                      <input
                        type="radio"
                        name="origin-airport"
                        value={item.code}
                        checked={pickedCode === item.code}
                        onChange={() => onPickAirport(item)}
                        disabled={loading || choicesLoading}
                      />
                      <span>{radioLabel(item)}</span>
                    </label>
                  ))}
                </fieldset>
              )}
              {asking && (
                <div className="mt-3 flex gap-2">
                  <input
                    ref={bubbleInputRef}
                    value={bubbleDraft}
                    onChange={(e) => setBubbleDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        onBubbleSubmit();
                      }
                    }}
                    placeholder={
                      airportOptions || placeMiss
                        ? "Or type a city"
                        : slotPlaceholder(pendingNeed[0])
                    }
                    disabled={loading || choicesLoading}
                    className="min-w-0 flex-1 rounded-md border border-stone-300 px-3 py-2"
                  />
                  <button
                    type="button"
                    onClick={onBubbleSubmit}
                    disabled={loading || choicesLoading || !bubbleDraft.trim()}
                    className="rounded-md bg-amber-800 px-4 py-2 font-semibold text-white disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
              )}
            </div>
          )}

          {!asking && !blocked && showRoute && (
            <div className="rounded-xl bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-semibold">
                  {result.origin} → {result.destination} · {result.date}
                </span>
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
          )}

          {result.errors.length > 0 && (
            <ul className="rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-900">
              {result.errors.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          )}

          {!asking && !blocked && result.recommendations.length > 0 && (
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
                      <td className="px-4 py-2">{formatUSD(r.flight.price_vnd)}</td>
                      <td className="px-4 py-2 text-stone-600">{r.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!asking && !blocked && result.flights.length > 0 && (
            <details className="rounded-xl bg-white p-5 text-sm shadow-sm">
              <summary className="cursor-pointer font-semibold">All offers the agents read</summary>
              <ul className="mt-2 space-y-1 text-stone-700">
                {result.flights.map((f, i) => (
                  <li key={`${f.airline}-${f.departure_time}-${i}`}>
                    {result.date} · {f.departure_time} · {f.airline} · {formatUSD(f.price_vnd)} · {f.baggage}
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
