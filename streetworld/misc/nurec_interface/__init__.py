__all__ = ["SimulatorInterface"]


def __getattr__(name):
    if name == "SimulatorInterface":
        from .simulator_interface import SimulatorInterface

        return SimulatorInterface
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
