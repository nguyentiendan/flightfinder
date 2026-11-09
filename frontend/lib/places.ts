export type { PlaceAirport } from "./api";
import type { PlaceAirport } from "./api";

export function radioLabel(item: PlaceAirport): string {
  return `${item.city} (${item.code})`;
}

export function choiceQuestion(place: string, slot = "origin"): string {
  const name = place.trim() || "There";
  const where = slot === "destination" ? "to" : "from";
  return `${name} has several airports. Which city are you flying ${where}?`;
}

export function unknownPlaceQuestion(place: string): string {
  const name = place.trim() || "that place";
  return `I couldn't find airports for ${name}. Type a city name.`;
}
