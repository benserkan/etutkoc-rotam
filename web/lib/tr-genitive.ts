/** Kesme işaretli tamlayan eki: "Emir" → "Emir'in", "Ayşe" → "Ayşe'nin" (backend `genitive` ile aynı). */
export function trGenitive(name: string): string {
  const w = (name ?? "").trim();
  if (!w) return "Öğrencinin";
  const vowels = "aıoueiöü";
  const lower = w.toLocaleLowerCase("tr");
  const last = [...lower].reverse().find((c) => vowels.includes(c)) ?? "e";
  const v = ({ a: "ı", ı: "ı", o: "u", u: "u", e: "i", i: "i", ö: "ü", ü: "ü" } as Record<string, string>)[last];
  return `${w}'${vowels.includes(lower[lower.length - 1]) ? "n" : ""}${v}n`;
}

/** Ad soyaddan ilk ad. */
export function firstNameOf(full?: string | null): string {
  return (full ?? "").trim().split(/\s+/)[0] ?? "";
}
