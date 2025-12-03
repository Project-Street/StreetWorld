"""
Configuration management for StreetWorld.
This module provides a lightweight Config class to manage configuration dictionaries.
"""

import copy
from typing import Any, Dict, List, Optional, Union


class Config(dict):
    """
    A configuration class that extends dict to provide convenient config management.
    Supports merging configurations with optional key replacement.
    """

    def __init__(self, data: Optional[Union[Dict, "Config"]] = None):
        """
        Initialize Config from a dictionary or another Config object.

        Args:
            data: Dictionary or Config object to initialize from
        """
        super().__init__()
        if data is None:
            data = {}
        if isinstance(data, (dict, Config)):
            self.update(data)
        else:
            raise TypeError(f"Config must be initialized with dict or Config, got {type(data)}")

    def copy(self) -> "Config":
        """
        Create a deep copy of this Config object.

        Returns:
            A new Config object with deep copied data
        """
        return Config(copy.deepcopy(dict(self)))

    def merge_from(
        self,
        other_config: Union[Dict, "Config"],
        replace_keys: Optional[List[str]] = None,
    ) -> None:
        """
        Merge another configuration into this one.

        For keys in replace_keys, the values are completely replaced.
        For other keys, the merge is recursive for nested dicts.

        Args:
            other_config: Configuration to merge from
            replace_keys: List of keys that should be replaced entirely instead of merged recursively
        """
        if replace_keys is None:
            replace_keys = []

        for key, value in other_config.items():
            if key in replace_keys:
                # Replace the entire key
                self[key] = copy.deepcopy(value)
            elif key in self and isinstance(self[key], dict) and isinstance(value, dict):
                # Recursive merge for nested dicts
                if isinstance(self[key], Config):
                    self[key].merge_from(value, replace_keys=[])
                else:
                    # Convert nested dict to Config for consistency
                    nested_config = Config(self[key])
                    nested_config.merge_from(value, replace_keys=[])
                    self[key] = nested_config
            else:
                # Direct assignment for non-dict values or new keys
                self[key] = copy.deepcopy(value)
