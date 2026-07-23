from collections import deque

import numpy as np


class PIDController:
    def __init__(self, k_p, k_i, k_d):
        self.k_p = k_p
        self.k_i = k_i
        self.k_d = k_d
        self.errors = deque([0.0] * 50, maxlen=50)

    def step(self, error):
        self.errors.append(error)
        integral = np.mean(self.errors)
        derivative = self.errors[-1] - self.errors[-2]
        return self.k_p * error + self.k_i * integral + self.k_d * derivative

    def reset(self):
        self.errors = deque([0.0] * 50, maxlen=50)
