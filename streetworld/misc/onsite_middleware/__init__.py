"""
OnSite middleware package for StreetWorld integration.
"""

__all__ = ["OnSiteSwitch", "TERMINAL_TYPE", "SIM_STATE", "OnSiteScenarioEnv"]


def __getattr__(name):
    if name in {"OnSiteSwitch", "TERMINAL_TYPE", "SIM_STATE"}:
        from .onsite_switch import OnSiteSwitch, TERMINAL_TYPE, SIM_STATE

        return {
            "OnSiteSwitch": OnSiteSwitch,
            "TERMINAL_TYPE": TERMINAL_TYPE,
            "SIM_STATE": SIM_STATE,
        }[name]
    if name == "OnSiteScenarioEnv":
        from .onsite_scenario_env import OnSiteScenarioEnv

        return OnSiteScenarioEnv
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
