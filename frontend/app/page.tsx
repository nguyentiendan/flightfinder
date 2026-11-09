"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { FlightCard } from "../components/FlightCard";
import {
  formatUSD,
  lookupPlace,
  priceSourceBadge,
  streamSearch,
  type PlaceAirport,
  type ProgressEvent,
  type SearchResult,
} from "../lib/api";
import { shiftIsoDate } from "../lib/dates";
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

const PLACEHOLDER = "I want to fly from SaiGon to Narita at 2027/11/1";

const STARTERS = [
  "I want to fly from SaiGon to Narita at 2027/11/1",
  "Fly from Hanoi to Da Nang at 2027-06-15",
  "Ticket from Saigon to Tokyo Haneda at 2027-12-20",
];

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
  const sessionReady = Boolean(
    slotsRef.current.origin && slotsRef.current.destination && slotsRef.current.date,
  );

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
      } else {
        slotsRef.current = {
          origin: r.origin,
          destination: r.destination,
          date: r.date,
        };
        setSlotAnswers({ ...EMPTY_SLOTS });
        setPendingNeed(r.need_slots);
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

  function onStarter(text: string) {
    setMessage(text);
    void runSearch(text);
  }

  function onShiftDate(days: number) {
    const current = slotsRef.current.date || result?.date || "";
    if (!current) return;
    const next = shiftIsoDate(current, days);
    slotsRef.current = { ...slotsRef.current, date: next };
    setMessage(`try ${next} instead`);
    void runSearch(`try ${next} instead`);
  }

  function onCheaper() {
    setMessage("any cheaper flights?");
    void runSearch("any cheaper flights?");
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

  function bookUrl(detailUrl: string): string {
    if (result?.kayak_url) return result.kayak_url;
    const ota = result?.ota_links.find((link) => link.search_url)?.search_url;
    return ota || detailUrl;
  }

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <header className="rounded-3xl bg-sky-950 px-6 py-7 text-sky-50">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-sky-300">Flight finder</p>
        <h1 className="mt-2 text-2xl font-semibold">Tell me where you want to go</h1>
        <p className="mt-2 max-w-xl text-sm text-sky-100/80">
          I search live fares, then you confirm the price on an airline site. Say a new city or date
          to refine this trip — you do not have to start over.
        </p>
      </header>

      <form onSubmit={onSearch} className="mt-5 rounded-3xl bg-white p-5 text-slate-900 shadow-sm">
        <label className="block">
          <span className="mb-1 block text-sm font-medium text-slate-700">Ask the agent</span>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={3}
            placeholder={PLACEHOLDER}
            className="w-full rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-slate-900 placeholder:text-slate-400"
          />
        </label>
        <div className="mt-3 flex flex-wrap gap-2">
          {STARTERS.map((text) => (
            <button
              key={text}
              type="button"
              onClick={() => onStarter(text)}
              disabled={loading}
              className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-700 hover:border-sky-300 hover:text-sky-800 disabled:opacity-50"
            >
              {text.replace("I want to fly from ", "").replace("Fly from ", "")}
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={loading || !message.trim()}
          className="mt-4 rounded-full bg-sky-600 px-5 py-2.5 font-medium text-white hover:bg-sky-500 disabled:opacity-50"
        >
          {loading ? "Searching..." : "Search flights"}
        </button>
      </form>

      {error && (
        <p className="mt-4 rounded-2xl bg-amber-100 px-4 py-3 text-sm text-amber-950">{error}</p>
      )}

      {loading && progress.length > 0 && (
        <ol className="mt-4 space-y-2 rounded-3xl bg-white px-5 py-4 text-sm text-slate-700 shadow-sm">
          {progress.map((ev, index) => {
            const last = index === progress.length - 1;
            return (
              <li key={`${ev.step}-${index}`} className="flex items-start gap-3">
                <span
                  className={`mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                    last ? "bg-sky-500" : "bg-emerald-400"
                  }`}
                />
                <span className={last ? "font-medium text-slate-900" : "text-slate-500"}>
                  {ev.message}
                </span>
              </li>
            );
          })}
        </ol>
      )}

      {result && (
        <section className="mt-4 space-y-4">
          {(asking || blocked) && agentText && (
            <div className="rounded-3xl bg-white px-5 py-4 text-sm text-slate-800 shadow-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-sky-700">Agent</p>
              <p className="mt-2 whitespace-pre-line">{agentText}</p>
              {choicesLoading && <p className="mt-2 text-slate-500">Looking up airports...</p>}
              {asking && airportOptions && (
                <fieldset className="mt-3 space-y-2">
                  <legend className="sr-only">Airports</legend>
                  {airportOptions.map((item) => (
                    <label
                      key={item.code}
                      className="flex cursor-pointer items-center gap-2 rounded-xl border border-slate-200 px-3 py-2"
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
                    className="min-w-0 flex-1 rounded-xl border border-slate-200 px-3 py-2"
                  />
                  <button
                    type="button"
                    onClick={onBubbleSubmit}
                    disabled={loading || choicesLoading || !bubbleDraft.trim()}
                    className="rounded-full bg-sky-600 px-4 py-2 font-medium text-white disabled:opacity-50"
                  >
                    Send
                  </button>
                </div>
              )}
            </div>
          )}

          {!asking && !blocked && showRoute && (
            <div className="rounded-3xl bg-white p-5 text-slate-900 shadow-sm">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="text-lg font-semibold">
                  {displayCity(result.origin)} → {displayCity(result.destination)}
                </span>
                <span className="text-slate-500">{result.date}</span>
                {badge && (
                  <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-800">
                    {badge}
                  </span>
                )}
              </div>
              {sessionReady && (
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => onShiftDate(-1)}
                    disabled={loading}
                    className="rounded-full border border-slate-200 px-3 py-1 text-xs hover:border-sky-300"
                  >
                    Day before
                  </button>
                  <button
                    type="button"
                    onClick={() => onShiftDate(1)}
                    disabled={loading}
                    className="rounded-full border border-slate-200 px-3 py-1 text-xs hover:border-sky-300"
                  >
                    Day after
                  </button>
                  <button
                    type="button"
                    onClick={onCheaper}
                    disabled={loading}
                    className="rounded-full border border-slate-200 px-3 py-1 text-xs hover:border-sky-300"
                  >
                    Any cheaper?
                  </button>
                </div>
              )}
              <p className="mt-3 text-xs text-slate-500">
                Prices are estimates (about 25,000 VND per US$). The fare you pay is on the booking
                site.
              </p>
            </div>
          )}

          {result.errors.length > 0 && (
            <ul className="rounded-2xl bg-amber-100 px-4 py-3 text-sm text-amber-950">
              {result.errors.map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ul>
          )}

          {!asking && !blocked && result.recommendations.length > 0 && (
            <div className="space-y-3">
              {result.recommendations.map((r, index) => (
                <FlightCard
                  key={r.label}
                  flight={r.flight}
                  date={result.date}
                  label={r.label}
                  reason={r.reason}
                  bookUrl={bookUrl(r.flight.detail_url)}
                  featured={index === 0}
                />
              ))}
            </div>
          )}

          {!asking && !blocked && result.flights.length > 0 && (
            <details className="rounded-3xl bg-white p-5 text-sm text-slate-700 shadow-sm">
              <summary className="cursor-pointer font-medium text-slate-900">All offers</summary>
              <ul className="mt-3 space-y-2">
                {result.flights.map((f, i) => (
                  <li
                    key={`${f.airline}-${f.departure_time}-${i}`}
                    className="flex flex-wrap items-baseline justify-between gap-2 border-t border-slate-100 pt-2"
                  >
                    <span>
                      {f.departure_time}
                      {f.arrival_time ? ` → ${f.arrival_time}` : ""} · {f.airline} · {f.baggage}
                    </span>
                    <span className="font-medium text-slate-900">{formatUSD(f.price_vnd)}</span>
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
