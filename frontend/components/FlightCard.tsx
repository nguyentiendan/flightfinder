import { formatUSD, type Flight } from "../lib/api";
import { formatDuration, stopsLabel } from "../lib/dates";

export function FlightCard({
  flight,
  date,
  label,
  reason,
  bookUrl,
  featured,
}: {
  flight: Flight;
  date: string;
  label?: string;
  reason?: string;
  bookUrl: string;
  featured?: boolean;
}) {
  const duration = formatDuration(flight.duration_minutes);
  const timeLine = flight.arrival_time
    ? `${flight.departure_time} → ${flight.arrival_time}`
    : flight.departure_time;

  return (
    <article
      className={`rounded-2xl border bg-white p-4 shadow-sm ${
        featured ? "border-sky-400 ring-1 ring-sky-200" : "border-slate-200"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {label && (
            <p className="text-xs font-medium uppercase tracking-wide text-sky-700">{label}</p>
          )}
          <p className="mt-1 text-lg font-semibold text-slate-900">{timeLine}</p>
          <p className="text-sm text-slate-600">
            {flight.airline}
            {" · "}
            {stopsLabel(flight.stops)}
            {duration ? ` · ${duration}` : ""}
          </p>
          <p className="mt-1 text-xs text-slate-500">
            {date}
            {flight.baggage ? ` · ${flight.baggage}` : ""}
            {flight.refundable ? " · refundable" : ""}
          </p>
          {reason && <p className="mt-2 text-sm text-slate-600">{reason}</p>}
        </div>
        <div className="text-right">
          <p className="text-xl font-semibold text-slate-900">{formatUSD(flight.price_vnd)}</p>
          {bookUrl && (
            <a
              href={bookUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-2 inline-flex rounded-full bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500"
            >
              Check price
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
