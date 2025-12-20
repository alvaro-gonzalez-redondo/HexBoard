import math
from math import gcd
from dataclasses import dataclass
from typing import Optional

# ============================================================
# CONFIGURACIÓN GLOBAL
# ============================================================

EDOS = [12, 17, 19, 22, 24, 31, 41, 43, 46, 53, 58, 72, 80, 87]

# Umbral máximo absoluto si no encaja en nada
MAX_COMPLEX_ERROR_CENTS = 50.0

# Umbral por prime-limit (en cents)
MAX_ERROR_BY_LIMIT = {
    1: 5,
    3: 20,
    5: 25,
    7: 25,
    11: 30,
    13: 35,
    17: 15,
}

# ============================================================
# VOCABULARIO DE RATIOS (normalizado luego)
# ============================================================

RAW_ALLOWED_RATIOS = [
    # 1-limit
    (1, 1),
    (2, 1),

    # 3-limit
    (3, 2),
    (4, 3),
    (9, 8),
    (16, 9),

    # 5-limit
    (5, 4),
    (6, 5),
    (16, 15),
    (8, 5),
    (5, 3),
    (15, 8),

    # 7-limit
    (7, 4),
    (8, 7),
    (7, 6),
    (9, 7),
    (7, 5),
    (10, 7),
    (14, 9),
    (12, 7),

    # 11-limit
    (11, 8),
    (12, 11),
    (14, 11),
    (16, 11),
    (11, 7),

    # 13-limit
    (13, 8),
    (16, 13),

    # 17-limit
    (17, 16),
]

# ============================================================
# HELPERS ARMÓNICOS
# ============================================================

def prime_limit_of_int(n: int) -> Optional[int]:
    if n <= 0:
        return None
    while n % 2 == 0:
        n //= 2
    for p in (17, 13, 11, 7, 5, 3):
        if n % p == 0:
            return p
    return 1


def reduce_ratio(n: int, d: int) -> tuple[int, int]:
    g = gcd(n, d)
    return n // g, d // g


def normalize_to_octave(n: int, d: int) -> tuple[int, int]:
    n, d = reduce_ratio(n, d)
    while n < d:
        n *= 2
    while n >= 2 * d:
        d *= 2
    return reduce_ratio(n, d)


def ratio_to_cents(n: int, d: int) -> float:
    return 1200.0 * math.log2(n / d)


def ratio_prime_limit(n: int, d: int) -> Optional[int]:
    lim_n = prime_limit_of_int(n)
    lim_d = prime_limit_of_int(d)
    if lim_n is None or lim_d is None:
        return None
    return max(lim_n, lim_d)


# ============================================================
# CANDIDATOS ARMÓNICOS
# ============================================================

@dataclass(frozen=True)
class RatioCand:
    n: int
    d: int
    limit: int
    cents: float


def build_candidates(raw_ratios) -> list[RatioCand]:
    seen = set()
    cands: list[RatioCand] = []

    for n, d in raw_ratios:
        n, d = normalize_to_octave(n, d)
        key = (n, d)
        if key in seen:
            continue
        seen.add(key)

        lim = ratio_prime_limit(n, d)
        if lim is None or lim > 17:
            continue

        cands.append(RatioCand(
            n=n,
            d=d,
            limit=lim,
            cents=ratio_to_cents(n, d)
        ))

    # Orden estable: primero más simple (menor prime-limit)
    cands.sort(key=lambda r: (r.limit, r.cents))
    return cands


# ============================================================
# GENERACIÓN DE LUT POR EDO
# ============================================================

@dataclass
class HarmonicStep:
    limit_enum: str
    ideal_step: int
    max_error_steps: int


def build_lut_for_edo(edo: int, candidates: list[RatioCand]) -> list[HarmonicStep]:
    step_cents = 1200.0 / edo
    lut: list[HarmonicStep] = []

    for step in range(edo):
        sc = step * step_cents
        best = None  # (limit, error_cents, ideal_step)

        for r in candidates:
            max_err_cents = MAX_ERROR_BY_LIMIT.get(r.limit, 0)
            err = abs(sc - r.cents)
            err = min(err, 1200.0 - err)

            if err > max_err_cents:
                continue

            ideal = round(edo * math.log2(r.n / r.d)) % edo

            if best is None or (r.limit < best[0]) or (r.limit == best[0] and err < best[1]):
                best = (r.limit, err, ideal)

        if best is None:
            max_err_steps = max(1, math.ceil(MAX_COMPLEX_ERROR_CENTS / step_cents))
            lut.append(HarmonicStep(
                "LIMIT_COMPLEX",
                step,
                max_err_steps
            ))
        else:
            lim, err, ideal = best
            max_err_steps = max(1, math.ceil(MAX_ERROR_BY_LIMIT[lim] / step_cents))
            lut.append(HarmonicStep(
                f"LIMIT_{lim}",
                ideal,
                max_err_steps
            ))

    return lut


# ============================================================
# EMISIÓN C++
# ============================================================

def emit_cpp_luts(edos):
    candidates = build_candidates(RAW_ALLOWED_RATIOS)

    for edo in edos:
        lut = build_lut_for_edo(edo, candidates)

        print(f"// =======================")
        print(f"// Harmonic LUT for {edo}-EDO")
        print(f"// =======================")
        print(f"constexpr HarmonicStep harmonicLUT_{edo}[{edo}] = {{")
        for h in lut:
            print(f"    {{ {h.limit_enum}, {h.ideal_step}, {h.max_error_steps} }},")
        print("};\n")

    # Descriptor table
    print("// =======================")
    print("// Harmonic LUT descriptors")
    print("// =======================")
    print("constexpr HarmonicLUTDesc HARMONIC_LUTS[] = {")
    for edo in edos:
        print(f"    {{ {edo}, harmonicLUT_{edo} }},")
    print("};")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    emit_cpp_luts(EDOS)
