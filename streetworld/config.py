"""
Simplified Config system for StreetWorld.
Extracted and simplified from EasyDrive's engine.config module.
"""

from typing import Union, Dict, Any
from copy import deepcopy
from addict import Dict as AddictDict


class ConfigDict(AddictDict):
    """Extended Dict with attribute access support."""

    def __missing__(self, name):
        raise KeyError(name)

    def __getattr__(self, name):
        try:
            value = super().__getattr__(name)
        except KeyError:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
        else:
            return value


class Config:
    """
    A facility for config management.

    Simplified version of EasyDrive's Config class.
    Supports dict-like and attribute-like access to config values.

    Example:
        >>> cfg = Config(dict(a=1, b=dict(b1=[0, 1])))
        >>> cfg.a
        1
        >>> cfg.b
        {'b1': [0, 1]}
        >>> cfg.b.b1
        [0, 1]
    """

    def __init__(self, cfg_dict: Union[Dict, None] = None, **kwargs):
        """
        Initialize Config.

        Args:
            cfg_dict: Dictionary containing config values
            **kwargs: Additional config values as keyword arguments
        """
        if cfg_dict is None:
            cfg_dict = {}
        elif not isinstance(cfg_dict, dict):
            raise TypeError(f"cfg_dict must be a dict, but got {type(cfg_dict)}")

        # Merge kwargs into cfg_dict
        if kwargs:
            cfg_dict = dict(cfg_dict)  # Make a copy to avoid modifying original
            cfg_dict.update(kwargs)

        super().__setattr__("_cfg_dict", ConfigDict(cfg_dict))

    @property
    def filename(self):
        """Return filename if loaded from file, otherwise None."""
        return getattr(self, "_filename", None)

    @filename.setter
    def filename(self, value):
        super().__setattr__("_filename", value)

    def __len__(self):
        return len(self._cfg_dict)

    def __getattr__(self, name):
        return getattr(self._cfg_dict, name)

    def __getitem__(self, name):
        return self._cfg_dict.__getitem__(name)

    def __setattr__(self, name, value):
        if isinstance(value, dict):
            value = ConfigDict(value)
        self._cfg_dict.__setattr__(name, value)

    def __setitem__(self, name, value):
        if isinstance(value, dict):
            value = ConfigDict(value)
        self._cfg_dict.__setitem__(name, value)

    def __iter__(self):
        return iter(self._cfg_dict)

    def __repr__(self):
        return f"Config: {self._cfg_dict.__repr__()}"

    def __contains__(self, key):
        return key in self._cfg_dict

    def keys(self):
        """Return config keys."""
        return self._cfg_dict.keys()

    def values(self):
        """Return config values."""
        return self._cfg_dict.values()

    def items(self):
        """Return config items."""
        return self._cfg_dict.items()

    def get(self, key, default=None):
        """Get config value with default."""
        return self._cfg_dict.get(key, default)

    def copy(self):
        """Return a copy of the config."""
        return Config(deepcopy(dict(self._cfg_dict)))

    def merge_from(
        self, options: Dict, allow_list_keys: bool = True, replace_keys: list = None
    ):
        """
        Merge dict into cfg_dict.

        Args:
            options: Dictionary of configs to merge from
            allow_list_keys: If True, int string keys (e.g. '0', '1') are allowed
            replace_keys: Keys to replace instead of merge (no recursive merge)
        """
        if replace_keys is None:
            replace_keys = []
        option_cfg_dict = {}
        for full_key, v in options.items():
            d = option_cfg_dict
            key_list = full_key.split(".")
            for subkey in key_list[:-1]:
                d.setdefault(subkey, ConfigDict())
                d = d[subkey]
            subkey = key_list[-1]
            d[subkey] = v

        cfg_dict = super().__getattribute__("_cfg_dict")
        merged = self.__merge_a_into_b(
            option_cfg_dict, cfg_dict, allow_list_keys, replace_keys=replace_keys
        )
        super().__setattr__("_cfg_dict", ConfigDict(merged))

    @staticmethod
    def __merge_a_into_b(
        a: Dict, b: Dict, allow_list_keys: bool = True, replace_keys: list = None
    ) -> Dict:
        """
        Merge dict a into dict b (non-inplace).

        Values in a will overwrite b. b is copied first to avoid in-place modifications.

        Args:
            a: Source dict to be merged into b
            b: Origin dict
            allow_list_keys: If True, int string keys are allowed in source a
            replace_keys: Keys to replace instead of merge (no recursive merge)

        Returns:
            Modified dict of b using a
        """
        if replace_keys is None:
            replace_keys = []
        b = b.copy()

        for k, v in a.items():
            # If key is in replace_keys, directly replace instead of recursive merge
            if k in replace_keys:
                b[k] = v
                continue
            if allow_list_keys and k.isdigit() and isinstance(b, list):
                k = int(k)
                if k == len(b):
                    b.append(v)
                elif k > len(b):
                    raise KeyError(f"Index {k} exceeds the length of list {b}")
            elif isinstance(v, dict):
                if ((k in b) or (isinstance(b, list) and k <= len(b))):
                    allowed_types = (dict, list) if allow_list_keys else dict
                    if not isinstance(b[k], allowed_types):
                        raise TypeError(
                            f"{k}={v} in child config cannot inherit from "
                            f"base because {k} is a dict in the child config "
                            f"but is of type {type(b[k])} in base config."
                        )
                    b[k] = Config.__merge_a_into_b(v, b[k], allow_list_keys)
                else:
                    b[k] = ConfigDict(v)
            else:
                b[k] = v
        return b

    def to_dict(self):
        """Convert Config to plain dict."""
        return dict(self._cfg_dict)

    @classmethod
    def fromfile(cls, filename: str):
        """
        Load config from file.

        Supports .py, .json, .yaml, .yml formats.

        Args:
            filename: Path to config file

        Returns:
            Config object
        """
        import os
        import sys
        import tempfile
        import ast

        if not os.path.exists(filename):
            raise FileNotFoundError(f"Config file {filename} not found")

        file_ext = os.path.splitext(filename)[1].lower()

        if file_ext == '.py':
            cls.__validate_py_syntax(filename)
            # For .py files, import as a module
            with tempfile.TemporaryDirectory() as temp_dir:
                mod_name = os.path.splitext(os.path.basename(filename))[0]
                mod_path = os.path.dirname(filename)
                sys.path.insert(0, mod_path)
                sys.path.insert(0, temp_dir)

                # Copy file to temp dir to avoid import conflicts
                import shutil
                temp_file = os.path.join(temp_dir, os.path.basename(filename))
                shutil.copy(filename, temp_file)

                import importlib.util
                spec = importlib.util.spec_from_file_location(mod_name, temp_file)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)

                cfg_dict = {
                    name: value
                    for name, value in mod.__dict__.items()
                    if not name.startswith("__")
                    and not isinstance(value, type(importlib))
                }

                # Clean up
                del sys.modules[mod_name]
                sys.path.remove(mod_path)
                sys.path.remove(temp_dir)

        elif file_ext in ['.yaml', '.yml']:
            import yaml
            with open(filename, 'r') as f:
                cfg_dict = yaml.safe_load(f) or {}

        elif file_ext == '.json':
            import json
            with open(filename, 'r') as f:
                cfg_dict = json.load(f)
        else:
            raise OSError(f"Unsupported config file format: {file_ext}")

        cfg = cls(cfg_dict)
        cfg.filename = filename
        return cfg

    @staticmethod
    def __validate_py_syntax(filename):
        """Validate Python syntax of config file."""
        with open(filename, encoding="utf-8") as f:
            content = f.read()
        try:
            ast.parse(content)
        except SyntaxError as e:
            raise SyntaxError(f"There are syntax errors in config file {filename}: {e}")
