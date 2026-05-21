import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Tailwind class'larını çakışmaları çözerek birleştir.
 * Örn: cn("p-2", "p-4") → "p-4" (ikincisi galip).
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
