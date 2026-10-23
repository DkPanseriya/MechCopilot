"""
1D Euler–Bernoulli beam solver (finite elements, numpy).

Two-node Hermite elements (deflection v + rotation θ per node). The mesh has a
node at every support, load point and distributed-load boundary, so nodal
results are exact for the load types supported here. Internal shear and moment
are then recovered by statics from the solved reactions (exact, no element
recovery error), and deflection is Hermite-interpolated between nodes.

Sign conventions (all SI):
  * Forces and distributed loads are given DOWNWARD positive (gravity).
  * Point moments are given COUNTER-CLOCKWISE positive.
  * Reactions are reported UPWARD positive; reaction moments counter-clockwise.
  * Shear V: positive when the resultant of forces left of the section acts up.
  * Moment M: sagging positive (tension at the bottom fibre).
  * Deflection v: upward positive (a sagging beam has negative v).
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..core import CalcError


@dataclass
class Support:
    x: float
    kind: str  # "fixed" | "pinned" | "roller"


@dataclass
class PointLoad:
    x: float
    P: float   # N, downward positive


@dataclass
class PointMoment:
    x: float
    M: float   # N·m, counter-clockwise positive


@dataclass
class DistLoad:
    a: float
    b: float
    wa: float  # N/m at x=a, downward positive
    wb: float  # N/m at x=b

    def w(self, x: float) -> float:
        if self.b == self.a:
            return self.wa
        return self.wa + (self.wb - self.wa) * (x - self.a) / (self.b - self.a)


@dataclass
class BeamResult:
    x: np.ndarray
    V: np.ndarray
    M: np.ndarray
    v: np.ndarray
    theta: np.ndarray
    reactions: List[Dict[str, Optional[float]]] = field(default_factory=list)

    def _ext(self, arr):
        i = int(np.argmax(np.abs(arr)))
        return float(arr[i]), float(self.x[i])

    @property
    def M_max(self):
        """(signed value, position) of the largest |M|."""
        return self._ext(self.M)

    @property
    def V_max(self):
        return self._ext(self.V)

    @property
    def v_max(self):
        return self._ext(self.v)


def _element_stiffness(L: float, EI: float) -> np.ndarray:
    return EI / L ** 3 * np.array([
        [12, 6 * L, -12, 6 * L],
        [6 * L, 4 * L ** 2, -6 * L, 2 * L ** 2],
        [-12, -6 * L, 12, -6 * L],
        [6 * L, 2 * L ** 2, -6 * L, 4 * L ** 2],
    ])


def _consistent_load(L: float, q1: float, q2: float) -> np.ndarray:
    """Equivalent nodal loads for a linearly varying load q1→q2 (upward positive)."""
    return L / 20 * np.array([
        7 * q1 + 3 * q2,
        L * (3 * q1 + 2 * q2) / 3,
        3 * q1 + 7 * q2,
        -L * (2 * q1 + 3 * q2) / 3,
    ])


def solve_beam(L: float, EI: float, supports: List[Support],
               point_loads: List[PointLoad] = (), moments: List[PointMoment] = (),
               dist_loads: List[DistLoad] = (), n_elem: int = 80,
               n_samples: int = 201) -> BeamResult:
    if L <= 0:
        raise CalcError("Beam length must be positive.")
    if EI <= 0:
        raise CalcError("Bending stiffness EI must be positive.")
    if not supports:
        raise CalcError("The beam needs at least one support.")
    tol = 1e-9 * L
    for s in supports:
        if s.x < -tol or s.x > L + tol:
            raise CalcError("A support lies outside the beam.")
    for p in point_loads:
        if p.x < -tol or p.x > L + tol:
            raise CalcError(f"Point load at x = {p.x:.3g} m lies outside the beam (0–{L:.3g} m).")
    for m in moments:
        if m.x < -tol or m.x > L + tol:
            raise CalcError("A point moment lies outside the beam.")
    for d in dist_loads:
        if d.a < -tol or d.b > L + tol or d.b <= d.a:
            raise CalcError("A distributed load must start before it ends and lie on the beam.")

    # --- mesh ---------------------------------------------------------------
    keys = {0.0, L}
    keys.update(min(max(s.x, 0.0), L) for s in supports)
    keys.update(min(max(p.x, 0.0), L) for p in point_loads)
    keys.update(min(max(m.x, 0.0), L) for m in moments)
    for d in dist_loads:
        keys.update((d.a, d.b))
    keys = sorted(keys)
    merged = [keys[0]]
    for k in keys[1:]:
        if k - merged[-1] > tol:
            merged.append(k)
    h = L / n_elem
    nodes = [merged[0]]
    for a, b in zip(merged[:-1], merged[1:]):
        n = max(1, int(np.ceil((b - a) / h)))
        nodes.extend(a + (b - a) * (i + 1) / n for i in range(n))
    nodes = np.array(nodes)
    N = len(nodes)

    def node_of(x: float) -> int:
        return int(np.argmin(np.abs(nodes - x)))

    # --- assembly -----------------------------------------------------------
    K = np.zeros((2 * N, 2 * N))
    F = np.zeros(2 * N)
    for e in range(N - 1):
        x1, x2 = nodes[e], nodes[e + 1]
        Le = x2 - x1
        dofs = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(dofs, dofs)] += _element_stiffness(Le, EI)
        for d in dist_loads:
            if x1 >= d.a - tol and x2 <= d.b + tol:
                F[dofs] += _consistent_load(Le, -d.w(x1), -d.w(x2))
    for p in point_loads:
        F[2 * node_of(p.x)] += -p.P
    for m in moments:
        F[2 * node_of(m.x) + 1] += m.M

    fixed_dofs: List[int] = []
    for s in supports:
        i = node_of(s.x)
        if s.kind == "fixed":
            fixed_dofs += [2 * i, 2 * i + 1]
        elif s.kind in ("pinned", "roller"):
            fixed_dofs.append(2 * i)
        else:
            raise CalcError(f"Unknown support type '{s.kind}'.")
    fixed_dofs = sorted(set(fixed_dofs))
    free = np.setdiff1d(np.arange(2 * N), fixed_dofs)

    # Rigid-body modes of a transversely loaded beam are translation + rotation:
    # stable iff a fixed end exists or vertical restraint at two distinct points.
    restrained_x = {round(float(nodes[node_of(s.x)]), 12) for s in supports}
    if not any(s.kind == "fixed" for s in supports) and len(restrained_x) < 2:
        raise CalcError("The beam is unstable with these supports (it can rotate or translate as a "
                        "rigid body). Add a second support or use a fixed end.")
    Kff = K[np.ix_(free, free)]
    u = np.zeros(2 * N)
    u[free] = np.linalg.solve(Kff, F[free])
    R = K @ u - F

    reactions = []
    for s in supports:
        i = node_of(s.x)
        reactions.append({
            "x": float(nodes[i]), "kind": s.kind,
            "R": float(R[2 * i]),
            "M": float(R[2 * i + 1]) if s.kind == "fixed" else None,
        })

    # --- internal forces by statics ------------------------------------------
    forces = [(r["x"], r["R"]) for r in reactions] + [(p.x, -p.P) for p in point_loads]
    couples = [(r["x"], r["M"]) for r in reactions if r["M"] is not None] + \
              [(m.x, m.M) for m in moments]

    def internal(x: float, inclusive: bool):
        left = (lambda xi: xi <= x + tol) if inclusive else (lambda xi: xi < x - tol)
        V = sum(f for xi, f in forces if left(xi))
        Mx = sum(f * (x - xi) for xi, f in forces if left(xi))
        Mx -= sum(c for xi, c in couples if left(xi))
        for d in dist_loads:
            c = min(d.b, x)
            if c <= d.a:
                continue
            # upward q(s) = -(wa + k (s - a)) over [a, c]
            k = (d.wb - d.wa) / (d.b - d.a)
            R_ = d.wa * (c - d.a) + k * (c - d.a) ** 2 / 2
            Rs = d.wa * (c ** 2 - d.a ** 2) / 2 + k * ((c ** 3 - d.a ** 3) / 3 - d.a * (c ** 2 - d.a ** 2) / 2)
            V -= R_
            Mx -= x * R_ - Rs
        return V, Mx

    jumps = sorted({xi for xi, _ in forces} | {xi for xi, _ in couples})
    eps = 1e-6 * L
    xs = set(np.linspace(0.0, L, n_samples).tolist())
    for j in jumps:
        for xx in (j - eps, j + eps):
            if 0.0 < xx < L:
                xs.add(xx)
    xs = sorted(xs)
    V_arr, M_arr = [], []
    for k, xx in enumerate(xs):
        Vx, Mx = internal(xx, inclusive=(k == len(xs) - 1))
        V_arr.append(Vx)
        M_arr.append(Mx)
    xs_arr = np.array(xs)

    # --- deflection (Hermite interpolation) ---------------------------------
    v_nodes, t_nodes = u[0::2], u[1::2]
    idx = np.clip(np.searchsorted(nodes, xs_arr, side="right") - 1, 0, N - 2)
    x1, x2 = nodes[idx], nodes[idx + 1]
    Le = x2 - x1
    xi = (xs_arr - x1) / Le
    N1, N2 = 1 - 3 * xi ** 2 + 2 * xi ** 3, Le * (xi - 2 * xi ** 2 + xi ** 3)
    N3, N4 = 3 * xi ** 2 - 2 * xi ** 3, Le * (-xi ** 2 + xi ** 3)
    v = N1 * v_nodes[idx] + N2 * t_nodes[idx] + N3 * v_nodes[idx + 1] + N4 * t_nodes[idx + 1]
    dN1, dN2 = (-6 * xi + 6 * xi ** 2) / Le, 1 - 4 * xi + 3 * xi ** 2
    dN3, dN4 = (6 * xi - 6 * xi ** 2) / Le, -2 * xi + 3 * xi ** 2
    theta = dN1 * v_nodes[idx] + dN2 * t_nodes[idx] + dN3 * v_nodes[idx + 1] + dN4 * t_nodes[idx + 1]

    return BeamResult(x=xs_arr, V=np.array(V_arr), M=np.array(M_arr), v=v, theta=theta,
                      reactions=reactions)
