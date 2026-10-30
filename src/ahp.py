"""Analytic Hierarchy Process (Saaty 1980): weights from pairwise judgments, with a consistency check.

An expert compares every pair of criteria once on Saaty's 1–9 scale ("A is 3 times as important as B" -> 3,
"B is 3 times as important as A" -> 1/3). The comparisons form a reciprocal matrix A; the weights are its
principal eigenvector, normalised to sum to 1. The consistency ratio CR = CI / RI with CI = (λmax − n) / (n − 1)
says how self-contradictory the answers are; Saaty accepts CR < 0.10. Several experts are combined by the
geometric mean of their judgments (aggregation of individual judgments, Aczél & Saaty 1983).

Plain Python on purpose: the method is short enough to read in one go.
"""
import math
from dataclasses import dataclass
from fractions import Fraction

# Saaty's scale: 1 equal, 3 moderate, 5 strong, 7 very strong, 9 extreme (2, 4, 6, 8 in between) and reciprocals.
SCALE = tuple(sorted({Fraction(1, k) for k in range(1, 10)} | {Fraction(k) for k in range(1, 10)}))
SCALE_LABELS = {1: "rovnako dôležité", 3: "mierne dôležitejšie", 5: "výrazne dôležitejšie",
                7: "veľmi výrazne dôležitejšie", 9: "extrémne dôležitejšie"}

# Random index RI for n criteria: mean CI of random reciprocal matrices (Saaty 1980, Table 7.1).
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}
CR_LIMIT = 0.10


class AHPError(ValueError):
    """Judgments that do not form a valid comparison matrix."""


@dataclass
class Result:
    criteria: list[str]
    weights: dict[str, float]
    lambda_max: float
    ci: float
    cr: float

    @property
    def consistent(self) -> bool:
        return self.cr < CR_LIMIT


def pairs(criteria: list[str]) -> list[tuple[str, str]]:
    """Every comparison an expert answers, in a fixed order: (A, B) for A before B in the list."""
    return [(a, b) for i, a in enumerate(criteria) for b in criteria[i + 1:]]


def on_scale(value: float) -> bool:
    return any(math.isclose(value, float(s), rel_tol=1e-6) for s in SCALE)


def matrix(criteria: list[str], judgments: dict[str, float]) -> list[list[float]]:
    """Build the reciprocal matrix from judgments keyed "A|B" = how much more important A is than B."""
    n = len(criteria)
    if n < 2:
        raise AHPError("AHP needs at least two criteria")
    m = [[1.0] * n for _ in range(n)]
    for i, j in ((i, j) for i in range(n) for j in range(i + 1, n)):
        key = f"{criteria[i]}|{criteria[j]}"
        if key not in judgments:
            raise AHPError(f"missing judgment {key}")
        v = float(judgments[key])
        if v <= 0 or not on_scale(v):
            raise AHPError(f"{key}={v} is not on Saaty's 1–9 scale")
        m[i][j], m[j][i] = v, 1.0 / v
    extra = set(judgments) - {f"{a}|{b}" for a, b in pairs(criteria)}
    if extra:
        raise AHPError(f"unknown judgments: {', '.join(sorted(extra))}")
    return m


def principal_eigen(m: list[list[float]], tol: float = 1e-12, max_iter: int = 1000) -> tuple[list[float], float]:
    """Power iteration: for a positive reciprocal matrix it converges to the principal eigenvector (Perron)."""
    n = len(m)
    w = [1.0 / n] * n
    for _ in range(max_iter):
        nxt = [sum(m[i][j] * w[j] for j in range(n)) for i in range(n)]
        total = sum(nxt)
        nxt = [x / total for x in nxt]
        if max(abs(a - b) for a, b in zip(nxt, w)) < tol:
            w = nxt
            break
        w = nxt
    lam = sum(sum(m[i][j] * w[j] for j in range(n)) / w[i] for i in range(n)) / n
    return w, lam


def weigh(criteria: list[str], judgments: dict[str, float]) -> Result:
    m = matrix(criteria, judgments)
    w, lam = principal_eigen(m)
    n = len(criteria)
    ci = (lam - n) / (n - 1) if n > 2 else 0.0
    ri = RANDOM_INDEX.get(n)
    if ri is None:
        raise AHPError(f"no random index for {n} criteria (keep sets at 10 or fewer)")
    cr = ci / ri if ri else 0.0
    return Result(criteria, dict(zip(criteria, w)), lam, max(ci, 0.0), max(cr, 0.0))


def combine(criteria: list[str], experts: list[dict[str, float]]) -> dict[str, float]:
    """Geometric mean of each judgment across experts (keeps the matrix reciprocal)."""
    if not experts:
        raise AHPError("no expert judgments to combine")
    keys = [f"{a}|{b}" for a, b in pairs(criteria)]
    return {k: math.exp(sum(math.log(float(e[k])) for e in experts) / len(experts)) for k in keys}


@dataclass
class GroupResult:
    result: Result | None              # weights from the consistent experts combined
    individual: list[Result]           # every expert's own weights and CR, in input order
    used: list[int]                    # indexes of experts whose CR passed


def group(criteria: list[str], experts: list[dict[str, float]]) -> GroupResult:
    """Weights of a panel: each expert checked on its own, inconsistent ones (CR ≥ 0.10) left out."""
    individual = [weigh(criteria, e) for e in experts]
    used = [i for i, r in enumerate(individual) if r.consistent]
    if not used:
        return GroupResult(None, individual, used)
    combined = combine(criteria, [experts[i] for i in used])
    # The geometric mean of on-scale values is generally not on the scale; weigh it without the scale check.
    m = [[1.0] * len(criteria) for _ in criteria]
    for i, a in enumerate(criteria):
        for j, b in enumerate(criteria):
            if i < j:
                m[i][j], m[j][i] = combined[f"{a}|{b}"], 1.0 / combined[f"{a}|{b}"]
    w, lam = principal_eigen(m)
    n = len(criteria)
    ci = max((lam - n) / (n - 1), 0.0) if n > 2 else 0.0
    cr = ci / RANDOM_INDEX[n] if RANDOM_INDEX[n] else 0.0
    return GroupResult(Result(criteria, dict(zip(criteria, w)), lam, ci, cr), individual, used)


def equal(criteria: list[str]) -> dict[str, float]:
    """The documented default until a panel has answered (OECD/JRC Handbook 2008: equal weighting)."""
    return {c: 1.0 / len(criteria) for c in criteria}
