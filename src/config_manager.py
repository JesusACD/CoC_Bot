import copy

NON_OVERRIDABLE_KEYS = frozenset({
    "INSTANCE_IDS",
    "DEFAULT_INSTANCE_ID",
    "INSTANCE_CONFIGS",
})

# Maps id(cfg_module) -> deep copy of base uppercase config values before any overrides
_BASE_SNAPSHOTS = {}


def get_configs_module():
    try:
        import configs
        return configs
    except Exception:
        import configs_build as configs
        return configs


def _extract_config_keys(cfg):
    return {
        name: copy.deepcopy(getattr(cfg, name))
        for name in dir(cfg)
        if name.isupper() and name != "INSTANCE_CONFIGS"
    }


def snapshot_base_configs(cfg=None, force=False):
    """Capture base global config values once so instance overrides never leak across instances."""
    if cfg is None:
        cfg = get_configs_module()
    key = id(cfg)
    if force or key not in _BASE_SNAPSHOTS:
        _BASE_SNAPSHOTS[key] = _extract_config_keys(cfg)
    return _BASE_SNAPSHOTS[key]


def reset_base_configs(cfg=None):
    """Restore a configs module to its original global (base) values."""
    if cfg is None:
        cfg = get_configs_module()
    base = snapshot_base_configs(cfg)
    for name, value in base.items():
        setattr(cfg, name, copy.deepcopy(value))


def validate_instance_configs(cfg=None, logger=None):
    """Validate INSTANCE_CONFIGS structure and keys. Raises ValueError on invalid definitions."""
    if cfg is None:
        cfg = get_configs_module()
    base = snapshot_base_configs(cfg)
    instance_configs = getattr(cfg, "INSTANCE_CONFIGS", None)

    if instance_configs is None:
        return {}
    if not isinstance(instance_configs, dict):
        raise ValueError(
            "INSTANCE_CONFIGS must be a dict mapping instance IDs to override dicts."
        )

    valid_ids = set(getattr(cfg, "INSTANCE_IDS", []))
    for inst_id, overrides in instance_configs.items():
        if not isinstance(overrides, dict):
            raise ValueError(
                f"INSTANCE_CONFIGS['{inst_id}'] must be a dict of config overrides, "
                f"got {type(overrides).__name__}."
            )
        if valid_ids and inst_id not in valid_ids and logger is not None:
            logger.warning(
                f"INSTANCE_CONFIGS contains entry for '{inst_id}', which is not in INSTANCE_IDS."
            )
        for key in overrides:
            if key in NON_OVERRIDABLE_KEYS:
                raise ValueError(
                    f"Config '{key}' cannot be overridden per instance (instance '{inst_id}')."
                )
            if key not in base:
                raise ValueError(
                    f"Unknown config key '{key}' in INSTANCE_CONFIGS['{inst_id}']."
                )

    return instance_configs


def get_instance_config(instance_id, key, default=None, cfg=None):
    """Return the effective value of a single config key for `instance_id` without mutating global configs."""
    if cfg is None:
        cfg = get_configs_module()
    base = snapshot_base_configs(cfg)
    instance_configs = getattr(cfg, "INSTANCE_CONFIGS", None)

    if isinstance(instance_configs, dict) and instance_id in instance_configs:
        overrides = instance_configs[instance_id]
        if isinstance(overrides, dict) and key in overrides:
            return copy.deepcopy(overrides[key])

    if key in base:
        return copy.deepcopy(base[key])
    return default


def get_resolved_configs(instance_id, cfg=None, logger=None):
    """Return a full dict of effective config values for `instance_id` without mutating global configs."""
    if cfg is None:
        cfg = get_configs_module()
    base = snapshot_base_configs(cfg)
    instance_configs = validate_instance_configs(cfg=cfg, logger=logger)
    resolved = copy.deepcopy(base)
    if instance_id in instance_configs:
        for key, value in instance_configs[instance_id].items():
            resolved[key] = copy.deepcopy(value)
    return resolved


def apply_instance_configs(instance_id, cfg=None, logger=None):
    """Apply per-instance overrides for `instance_id` onto `cfg`, resetting to base defaults first."""
    if cfg is None:
        cfg = get_configs_module()
    instance_configs = validate_instance_configs(cfg=cfg, logger=logger)
    reset_base_configs(cfg)

    overrides = instance_configs.get(instance_id, {})
    for key, value in overrides.items():
        setattr(cfg, key, copy.deepcopy(value))

    if overrides and logger is not None:
        logger.info(
            f"Applied per-instance config overrides for '{instance_id}': {sorted(overrides.keys())}"
        )
    return copy.deepcopy(overrides)
