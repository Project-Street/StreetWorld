"""
Reference:
- Source: https://github.com/Bharath2/iLQR/blob/main/ilqr/containers.py
- Repository: Bharath2/iLQR
"""

import numpy as np
import sympy as sp
from numba import njit

from .utils import FiniteDiff, GetSyms, sympy_to_numba


class Dynamics:
    def __init__(self, f, f_x, f_u):
        self.f = f
        self.f_x = f_x
        self.f_u = f_u
        self.f_prime = njit(lambda x, u: (f_x(x, u), f_u(x, u)))

    @staticmethod
    def Discrete(f, x_eps=1e-4, u_eps=1e-4):
        f = njit(f, cache=True)
        f_x = njit(lambda x, u: FiniteDiff(f, x, u, 0, x_eps))
        f_u = njit(lambda x, u: FiniteDiff(f, x, u, 1, u_eps))
        return Dynamics(f, f_x, f_u)

    @staticmethod
    def SymDiscrete(f, x, u):
        f_x = f.jacobian(x)
        f_u = f.jacobian(u)

        f = sympy_to_numba(f, [x, u])
        f_x = sympy_to_numba(f_x, [x, u])
        f_u = sympy_to_numba(f_u, [x, u])

        return Dynamics(f, f_x, f_u)

    @staticmethod
    def Continuous(f, dt=0.1, x_eps=1e-4, u_eps=1e-4):
        f = njit(f)
        f_d = lambda x, u: x + f(x, u) * dt
        return Dynamics.Discrete(f_d, x_eps, u_eps)

    @staticmethod
    def SymContinuous(f, x, u, dt=0.1):
        return Dynamics.SymDiscrete(x + f * dt, x, u)


class Cost:
    def __init__(self, L, L_x, L_u, L_xx, L_ux, L_uu, Lf, Lf_x, Lf_xx):
        self.L = L
        self.L_x = L_x
        self.L_u = L_u
        self.L_xx = L_xx
        self.L_ux = L_ux
        self.L_uu = L_uu
        self.L_prime = njit(lambda x, u: (L_x(x, u), L_u(x, u), L_xx(x, u), L_ux(x, u), L_uu(x, u)))

        self.Lf = Lf
        self.Lf_x = Lf_x
        self.Lf_xx = Lf_xx
        self.Lf_prime = njit(lambda x: (Lf_x(x), Lf_xx(x)))

    @staticmethod
    def Symbolic(L, Lf, x, u):
        L_M = sp.Matrix([L])
        Lf_M = sp.Matrix([Lf])

        L_x = L_M.jacobian(x)
        L_u = L_M.jacobian(u)
        L_xx = L_x.jacobian(x)
        L_ux = L_u.jacobian(x)
        L_uu = L_u.jacobian(u)

        Lf_x = Lf_M.jacobian(x)
        Lf_xx = Lf_x.jacobian(x)

        funs = [L, L_x, L_u, L_xx, L_ux, L_uu, Lf, Lf_x, Lf_xx]
        for i in range(9):
            args = [x, u] if i < 6 else [x]
            redu = 0 if i in [3, 4, 5, 8] else 1
            funs[i] = sympy_to_numba(funs[i], args, redu)

        return Cost(*funs)

    @staticmethod
    def QR(Q, R, QT, x_goal, add_on=0):
        x, u = GetSyms(Q.shape[0], R.shape[0])
        er = x - sp.Matrix(x_goal)
        L = er.T @ Q @ er + u.T @ R @ u
        Lf = er.T @ QT @ er
        return Cost.Symbolic(L[0] + add_on, Lf[0], x, u)
