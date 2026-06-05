/** Koşullu className birleştirici (NativeWind). Boş/false değerleri atar. */
export function cn(...inputs: (string | false | null | undefined)[]): string {
  return inputs.filter(Boolean).join(" ");
}
