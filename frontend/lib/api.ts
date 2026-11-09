export interface Flight {
  airline: string;
  departure_time: string;
  price_vnd: number;
  baggage: string;
  refundable: boolean;
  source_id: string;
  detail_url: string;
}

export interface Recommendation {
  label: string;
  flight: Flight;
  reason: string;
}

export interface OtaLink {
  source_id: string;
  label: string;
  search_url: string;
}

export interface SearchParams {
  origin: string;
  destination: string;
  date: string;
  message: string;
}

export interface SearchResult {
  origin: string;
  destination: string;
  date: string;
  need_slots: string[];
  intake_question: string;
  blocked: boolean;
  kayak_url: string;
  flights: Flight[];
  recommendations: Recommendation[];
  ota_links: OtaLink[];
  sources_selected: string[];
  fetched_at: string;
  price_source: string;
  llm_model: string;
  errors: string[];
}

export interface ProgressEvent {
  step: string;
  message: string;
  order: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function streamSearch(
  params: SearchParams,
  onProgress: (e: ProgressEvent) => void,
  signal: AbortSignal,
): Promise<SearchResult> {
  const q = new URLSearchParams({
    origin: params.origin,
    destination: params.destination,
    date: params.date,
    message: params.message,
  }).toString();
  const res = await fetch(`${API_URL}/api/search/stream?${q}`, { signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body?.detail === "string" ? body.detail : `Backend error: ${res.status}`,
    );
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  return new Promise((resolve, reject) => {
    const pump = async (): Promise<void> => {
      try {
        const { done, value } = await reader.read();
        if (done) {
          reject(new Error("Lost the connection while waiting for results"));
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const payload = JSON.parse(line.slice(6));
          if (payload.done === false || payload.error) {
            reject(
              new Error(
                typeof payload.error === "string" ? payload.error : "Backend error",
              ),
            );
            return;
          }
          if (payload.done) {
            resolve(payload.result as SearchResult);
            return;
          }
          onProgress(payload as ProgressEvent);
        }
        await pump();
      } catch (err) {
        reject(err);
      }
    };
    signal.addEventListener("abort", () => reader.cancel());
    pump();
  });
}

const VND_PER_USD = 25_000;

export function formatUSD(priceVnd: number): string {
  const usd = priceVnd / VND_PER_USD;
  return `US$ ${usd.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

const PRICE_SOURCE_BADGE: Record<string, string> = {
  "google-flights": "source: Google Flights",
  "amadeus-sandbox": "source: Amadeus sandbox",
  amadeus: "source: Amadeus",
  mock: "source: mock data",
};

export function priceSourceBadge(priceSource: string): string | null {
  if (!priceSource) return null;
  return PRICE_SOURCE_BADGE[priceSource] ?? `source: ${priceSource}`;
}

export type PlaceAirport = { code: string; city: string };

export type PlaceLookup = {
  kind: "ambiguous" | "city" | "unknown";
  airports: PlaceAirport[];
};

export async function lookupPlace(q: string, signal?: AbortSignal): Promise<PlaceLookup> {
  const res = await fetch(`${API_URL}/api/places?${new URLSearchParams({ q })}`, { signal });
  if (!res.ok) {
    throw new Error(`Backend error: ${res.status}`);
  }
  return res.json() as Promise<PlaceLookup>;
}
