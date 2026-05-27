"""
Reference:
- Source: https://github.com/Bharath2/iLQR/blob/main/ilqr/controller.py
- Repository: Bharath2/iLQR
"""

import numba
import numpy as np


class iLQR:
    def __init__(self, dynamics, cost):
        self.cost = cost
        self.dynamics = dynamics
        self.params = {
            "alphas": 0.5**np.arange(8),
            "regu_init": 20,
            "max_regu": 10000,
            "min_regu": 0.001,
        }

    def fit(self, x0, us_init, maxiters=50, early_stop=True):
        return run_ilqr(
            self.dynamics.f,
            self.dynamics.f_prime,
            self.cost.L,
            self.cost.Lf,
            self.cost.L_prime,
            self.cost.Lf_prime,
            x0,
            us_init,
            maxiters,
            early_stop,
            **self.params,
        )

    def rollout(self, x0, us):
        return rollout(self.dynamics.f, self.cost.L, self.cost.Lf, x0, us)


class MPC:
    def __init__(self, controller, control_horizon=1):
        self.ch = control_horizon
        self.controller = controller
        self.us_init = None

    def set_initial(self, us_init):
        if us_init.shape[0] <= self.ch:
            raise Exception("prediction horizon must be greater than control horizon")
        self.us_init = us_init

    def control(self, x0, maxiters=50, early_stop=True):
        if self.us_init is None:
            raise Exception("initial guess has not been set")
        _, us, _ = self.controller.fit(x0, self.us_init, maxiters, early_stop)
        self.us_init[:-self.ch] = self.us_init[self.ch:]
        return us[:self.ch]


@numba.njit
def run_ilqr(
    f,
    f_prime,
    L,
    Lf,
    L_prime,
    Lf_prime,
    x0,
    u_init,
    max_iters,
    early_stop,
    alphas,
    regu_init=20,
    max_regu=10000,
    min_regu=0.001,
):
    us = u_init
    regu = regu_init
    xs, J_old = rollout(f, L, Lf, x0, us)
    cost_trace = [J_old]

    for it in range(max_iters):
        ks, Ks, exp_cost_redu = backward_pass(f_prime, L_prime, Lf_prime, xs, us, regu)

        if it > 3 and early_stop and np.abs(exp_cost_redu) < 1e-5:
            break

        for alpha in alphas:
            xs_new, us_new, J_new = forward_pass(f, L, Lf, xs, us, ks, Ks, alpha)
            if J_old - J_new > 0:
                J_old = J_new
                xs = xs_new
                us = us_new
                regu *= 0.7
                break
        else:
            regu *= 2.0

        cost_trace.append(J_old)
        regu = min(max(regu, min_regu), max_regu)

    return xs, us, cost_trace


@numba.njit
def rollout(f, L, Lf, x0, us):
    xs = np.empty((us.shape[0] + 1, x0.shape[0]))
    xs[0] = x0
    cost = 0
    for n in range(us.shape[0]):
        xs[n + 1] = f(xs[n], us[n])
        cost += L(xs[n], us[n])
    cost += Lf(xs[-1])
    return xs, cost


@numba.njit
def forward_pass(f, L, Lf, xs, us, ks, Ks, alpha):
    xs_new = np.empty(xs.shape)

    cost_new = 0.0
    xs_new[0] = xs[0]
    us_new = us + alpha * ks

    for n in range(us.shape[0]):
        us_new[n] += Ks[n].dot(xs_new[n] - xs[n])
        xs_new[n + 1] = f(xs_new[n], us_new[n])
        cost_new += L(xs_new[n], us_new[n])

    cost_new += Lf(xs_new[-1])

    return xs_new, us_new, cost_new


@numba.njit
def backward_pass(f_prime, L_prime, Lf_prime, xs, us, regu):
    ks = np.empty(us.shape)
    Ks = np.empty((us.shape[0], us.shape[1], xs.shape[1]))

    delta_V = 0
    V_x, V_xx = Lf_prime(xs[-1])
    regu_I = regu * np.eye(V_xx.shape[0])
    for n in range(us.shape[0] - 1, -1, -1):
        f_x, f_u = f_prime(xs[n], us[n])
        l_x, l_u, l_xx, l_ux, l_uu = L_prime(xs[n], us[n])

        Q_x = l_x + f_x.T @ V_x
        Q_u = l_u + f_u.T @ V_x
        Q_xx = l_xx + f_x.T @ V_xx @ f_x
        Q_ux = l_ux + f_u.T @ V_xx @ f_x
        Q_uu = l_uu + f_u.T @ V_xx @ f_u

        f_u_dot_regu = f_u.T @ regu_I
        Q_ux_regu = Q_ux + f_u_dot_regu @ f_x
        Q_uu_regu = Q_uu + f_u_dot_regu @ f_u
        Q_uu_inv = np.linalg.inv(Q_uu_regu)

        k = -Q_uu_inv @ Q_u
        K = -Q_uu_inv @ Q_ux_regu
        ks[n], Ks[n] = k, K

        V_x = Q_x + K.T @ Q_u + Q_ux.T @ k + K.T @ Q_uu @ k
        V_xx = Q_xx + 2 * K.T @ Q_ux + K.T @ Q_uu @ K
        delta_V += Q_u.T @ k + 0.5 * k.T @ Q_uu @ k

    return ks, Ks, delta_V
