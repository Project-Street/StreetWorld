"""
Reference:
- Source: https://github.com/Bharath2/iLQR/blob/main/ilqr/utils.py
- Repository: Bharath2/iLQR
"""

import numpy as np
import sympy as sp
from numba import njit


def GetSyms(n_x, n_u):
    x = sp.IndexedBase("x")
    u = sp.IndexedBase("u")
    xs = sp.Matrix([x[i] for i in range(n_x)])
    us = sp.Matrix([u[i] for i in range(n_u)])
    return xs, us


def Constrain(cs, eps=1e-4):
    cost = 0
    for i in range(len(cs)):
        cost -= sp.log(cs[i] + eps)
    return 0.1 * cost


def Bounded(vars, high, low, *params):
    cs = []
    for i in range(len(vars)):
        diff = (high[i] - low[i]) / 2
        cs.append((high[i] - vars[i]) / diff)
        cs.append((vars[i] - low[i]) / diff)
    return Constrain(cs, *params)


def SoftConstrain(cs, alpha=0.01, beta=10):
    cost = 0
    for i in range(len(cs)):
        cost += alpha * sp.exp(-beta * cs[i])
    return cost


def Smooth_abs(x, alpha=0.25):
    return sp.sqrt(x**2 + alpha**2) - alpha


@njit
def FiniteDiff(fun, x, u, i, eps):
    args = (x, u)
    fun0 = fun(x, u)

    m = x.size
    n = args[i].size

    Jac = np.zeros((m, n))
    for k in range(n):
        args[i][k] += eps
        Jac[:, k] = (fun(args[0], args[1]) - fun0) / eps
        args[i][k] -= eps

    return Jac


def sympy_to_numba(f, args, redu=True):
    modules = [{"atan2": np.arctan2}, "numpy"]

    if isinstance(f, sp.Matrix):
        m, n = f.shape
        f += 1e-64 * np.ones((m, n))

        if (n == 1 or m == 1) and redu:
            if n == 1:
                f = f.T
            f = sp.Array(f)[0, :]
            f = njit(sp.lambdify(args, f, modules=modules))
            f_new = lambda *call_args: np.asarray(f(*call_args))
            return njit(f_new)

    f = sp.lambdify(args, f, modules=modules)
    return njit(f)
