"""Katman 5 — Saf-Python Mamdani fuzzy inference motoru.

Sıfır external bağımlılık. Üyelik fonksiyonu (triangular/trapezoidal),
fuzzy değişken, kural ve Mamdani çıkarımı + centroid defuzzification.

Kullanım örneği:

    fresh = FuzzyVariable("freshness", (0, 365))
    fresh.add_set("yeni",    triangle(0, 0, 60))
    fresh.add_set("eski",    triangle(180, 365, 365))

    out = FuzzyVariable("score", (0, 100))
    out.add_set("low",  triangle(0, 0, 50))
    out.add_set("high", triangle(50, 100, 100))

    engine = MamdaniInference(
        input_vars={"freshness": fresh},
        output_var=out,
        rules=[
            FuzzyRule([("freshness","yeni")], ("score","high")),
            FuzzyRule([("freshness","eski")], ("score","low")),
        ],
    )
    crisp, firings = engine.infer({"freshness": 30})

İmplementasyon notu:
- AND için min operatörü (Mamdani standart)
- Kuralın "clipped consequent"ı = min(firing_strength, consequent_membership)
- Aggregation: tüm clipped consequent'lerin max'ı (sup-min composition)
- Defuzzification: centroid (center of gravity)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


MembershipFn = Callable[[float], float]


# ---------------------------- Üyelik fonksiyonları ----------------------------


def triangle(a: float, b: float, c: float) -> MembershipFn:
    """Üçgen üyelik: a..b..c — 0 dışında, peak (1) at b.

    Dejenere kenarlar: a==b sol kenar dik (x=a=b'de 1'e atlar);
    b==c sağ kenar dik. Sınır noktalarında üyelik tanımı:
      x = a (a<b) → 0
      x = b      → 1
      x = c (c>b)→ 0
    """
    if not (a <= b <= c):
        raise ValueError(f"triangle: a({a}) <= b({b}) <= c({c}) olmalı")

    def f(x: float) -> float:
        if x < a or x > c:
            return 0.0
        if x == b:
            return 1.0
        if x < b:
            # b > a garantili (b==a olsaydı x==b dalı yakalardı)
            return (x - a) / (b - a)
        # x > b → düşen kenar; c > b garantili
        return (c - x) / (c - b)

    return f


def trapezoid(a: float, b: float, c: float, d: float) -> MembershipFn:
    """Trapez üyelik: a..b..c..d — plateau [b,c] arası 1.

    Dejenere kenarlar: a==b sol kenar dik (x=a'da 1); c==d sağ kenar dik.
    Plateau kontrolü ÖNCE çalışır → a==b veya c==d özel durumları
    doğru yakalanır.
    """
    if not (a <= b <= c <= d):
        raise ValueError(f"trapezoid: a<=b<=c<=d gerekiyor, got ({a},{b},{c},{d})")

    def f(x: float) -> float:
        if x < a or x > d:
            return 0.0
        if b <= x <= c:
            return 1.0
        if x < b:
            # b > a garantili (b==a olsaydı plateau yakalardı)
            return (x - a) / (b - a)
        # x > c → düşen kenar; d > c garantili
        return (d - x) / (d - c)

    return f


def singleton(value: float) -> MembershipFn:
    """Tek nokta üyelik: x == value ise 1, aksi 0. Kategorik girdiler için."""
    def f(x: float) -> float:
        return 1.0 if abs(x - value) < 1e-9 else 0.0
    return f


# ---------------------------- Veri sınıfları ----------------------------


@dataclass
class FuzzyVariable:
    """Bir linguistic değişken: alanı + üzerine tanımlı fuzzy küme(ler)."""
    name: str
    domain: tuple[float, float]
    sets: dict[str, MembershipFn] = field(default_factory=dict)

    def add_set(self, name: str, fn: MembershipFn) -> None:
        self.sets[name] = fn

    def fuzzify(self, value: float) -> dict[str, float]:
        """Crisp değer için her kümeye üyelik derecesini döner."""
        clamped = max(self.domain[0], min(self.domain[1], value))
        return {n: fn(clamped) for n, fn in self.sets.items()}


@dataclass
class FuzzyRule:
    """IF (var=set) AND (var=set) ... THEN output_var=set"""
    antecedents: list[tuple[str, str]]
    consequent: tuple[str, str]
    weight: float = 1.0

    def label(self) -> str:
        lhs = " AND ".join(f"{v}={s}" for v, s in self.antecedents)
        rhs = f"{self.consequent[0]}={self.consequent[1]}"
        w = f" (w={self.weight})" if self.weight != 1.0 else ""
        return f"{lhs} -> {rhs}{w}"


@dataclass
class InferenceResult:
    """Mamdani çıktısı + içgörü için per-kural ateşleme + ham aggregate."""
    crisp: float
    firings: list[tuple[FuzzyRule, float]]
    aggregate: list[float]
    domain_samples: list[float]


# ---------------------------- Mamdani çıkarımı ----------------------------


@dataclass
class MamdaniInference:
    input_vars: dict[str, FuzzyVariable]
    output_var: FuzzyVariable
    rules: list[FuzzyRule]
    resolution: int = 200  # defuzz integration grid

    def infer(self, inputs: dict[str, float]) -> InferenceResult:
        # 1) Fuzzification
        fuzzy_inputs: dict[str, dict[str, float]] = {}
        for name, var in self.input_vars.items():
            if name in inputs:
                fuzzy_inputs[name] = var.fuzzify(inputs[name])
            else:
                # Girdi verilmediyse tüm setler 0 — bu girdiye dayanan kural ateşlenmez
                fuzzy_inputs[name] = {n: 0.0 for n in var.sets}

        # 2) Rule firing strength (min t-norm)
        firings: list[tuple[FuzzyRule, float]] = []
        for rule in self.rules:
            strength = rule.weight
            for var_name, set_name in rule.antecedents:
                mu = fuzzy_inputs.get(var_name, {}).get(set_name, 0.0)
                strength = min(strength, mu)
                if strength == 0.0:
                    break
            firings.append((rule, strength))

        # 3) Aggregate output fuzzy set: per-grid-point, max over clipped consequents
        lo, hi = self.output_var.domain
        n = self.resolution
        step = (hi - lo) / n if n > 0 else 0.0
        domain_samples = [lo + i * step for i in range(n + 1)]
        aggregate = [0.0] * (n + 1)

        for rule, strength in firings:
            if strength == 0.0:
                continue
            out_set_name = rule.consequent[1]
            out_fn = self.output_var.sets.get(out_set_name)
            if out_fn is None:
                continue
            for i, x in enumerate(domain_samples):
                clipped = min(strength, out_fn(x))
                if clipped > aggregate[i]:
                    aggregate[i] = clipped

        # 4) Defuzzification — centroid (center of gravity)
        num = 0.0
        den = 0.0
        for x, mu in zip(domain_samples, aggregate):
            num += mu * x
            den += mu
        if den > 0:
            crisp = num / den
        else:
            crisp = (lo + hi) / 2  # hiç kural ateşlenmedi → orta nokta

        return InferenceResult(
            crisp=crisp,
            firings=firings,
            aggregate=aggregate,
            domain_samples=domain_samples,
        )
