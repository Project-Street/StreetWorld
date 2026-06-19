class StepCounter:
    def __init__(self, step_size, physical_repeat=0):
        self.step_size = step_size
        self.physical_repeat = physical_repeat

    def reset(self, timestamp_range, **kwargs):
        self.begin_timestamp = timestamp_range[0]
        self.end_timestamp = timestamp_range[1]
        self.physical_step = 0
    
    def step(self):
        self.physical_step += 1
        # assert self.current_timestamp > self.end_timestamp, "Counter exceed."
    
    @property
    def relative_timestamp(self):
        return self.physical_step * self.step_size

    @property
    def current_timestamp(self):
        return self.begin_timestamp + self.relative_timestamp

    @property
    def eposide_step(self):
        return self.physical_step // self.physical_repeat
