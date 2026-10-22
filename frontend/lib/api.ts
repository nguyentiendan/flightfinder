export interface Flight {
  airline: string;
  departure_time: string;
  price_vnd: number;
  baggage: string;
  detail_url: string;
}

export interface Recommendation {
  label: string;
  flight: Flight;
  reason: string;
}

export interface SearchResult {
  origin: string;
  destination: string;
  date: string;
  kayak_url: string;
  flights: Flight[];
  recommendations: Recommendation[];
  fetched_at: string;
  source: string;
  llm_model: string;
}

export interface ProgressEvent {
  step: string;
  message: string;
  order: string;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function streamSearch(
  params: { origin: string; destination: string; date: string },
  onProgress: (e: ProgressEvent) => void,
  signal: AbortSignal,
): Promise<SearchResult> {
  const q = new URLSearchParams(params).toString();
  const res = await fetch(`${API_URL}/api/search/stream?${q}`, { signal });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body?.detail === "string" ? body.detail : `Backend loi: ${res.status}`,
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
          reject(new Error("Mat ket noi khi dang nhan ket qua"));
          return;
        }
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((l) => l.startsWith("data: "));
          if (!line) continue;
          const payload = JSON.parse(line.slice(6));
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

export function formatVND(n: number): string {
  return `${(n / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tr`;
}
