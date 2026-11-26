import types
import pytest

import config_manager


def _make_fake_configs(**overrides):
    mod = types.SimpleNamespace(
        INSTANCE_IDS=["main", "th9", "th16"],
        DEFAULT_INSTANCE_ID="main",
        CHECK_INTERVAL=5,
        MAX_UPGRADES_PER_CHECK=10,
        OPEN_HOME_BUILDERS=0,
        OPEN_BUILDER_BUILDERS=0,
        UPGRADE_HEROES=True,
        UPGRADE_HOME_BASE=True,
        UPGRADE_HOME_LAB=True,
        UPGRADE_PETS=True,
        ASSIGN_LAB_ASSISTANT=True,
        ASSIGN_BUILDER_APPRENTICE=True,
        PRIORITY_HOME_BASE_UPGRADES=True,
        PRIORITY_HOME_LAB_UPGRADES=True,
        PRIORITY_PET_UPGRADES=True,
        PRIORITY_BUILDER_BASE_UPGRADES=True,
        PRIORITY_BUILDER_LAB_UPGRADES=True,
        UPGRADE_BUILDER_BASE=True,
        UPGRADE_BUILDER_LAB=True,
        ATTACK_HOME_BASE=True,
        ATTACK_BUILDER_BASE=True,
        TROOP_DEPLOY_TIME=2,
        ATTACK_SLOT_RANGE=(0, 100),
        EXCLUDE_CLAN_TROOPS=True,
        EMULATOR_TYPE="bluestacks",
        AUTO_START_EMULATOR=True,
        HOME_BASE_UPGRADE_PRIORITY=[["Laboratory", "Barbarian King"], ["Wall"]],
        HOME_LAB_UPGRADE_PRIORITY=[["Dragon", "Balloon"]],
        PET_HOUSE_UPGRADE_PRIORITY=[["Unicorn", "Phoenix"]],
        BUILDER_BASE_UPGRADE_PRIORITY=[["Builder Hall"]],
        BUILDER_LAB_UPGRADE_PRIORITY=[["Baby Dragon"]],
    )
    for k, v in overrides.items():
        setattr(mod, k, v)
    return mod


def test_missing_or_empty_instance_configs_keeps_defaults():
    cfg = _make_fake_configs()
    applied = config_manager.apply_instance_configs("main", cfg=cfg)
    assert applied == {}
    assert cfg.OPEN_HOME_BUILDERS == 0
    assert cfg.HOME_BASE_UPGRADE_PRIORITY == [["Laboratory", "Barbarian King"], ["Wall"]]


def test_apply_overrides_and_switch_instances_without_leaking():
    cfg = _make_fake_configs(
        INSTANCE_CONFIGS={
            "th9": {
                "OPEN_HOME_BUILDERS": 1,
                "UPGRADE_PETS": False,
                "HOME_BASE_UPGRADE_PRIORITY": [["Spell Factory", "Archer Queen"], ["Wall"]],
                "TROOP_DEPLOY_TIME": 1.5,
                "ATTACK_SLOT_RANGE": (0, 6),
            },
            "th16": {
                "OPEN_HOME_BUILDERS": 0,
                "PET_HOUSE_UPGRADE_PRIORITY": [["Spirit Fox", "Angry Jelly"]],
            },
        }
    )

    # Apply th9 overrides
    applied_th9 = config_manager.apply_instance_configs("th9", cfg=cfg)
    assert set(applied_th9.keys()) == {
        "OPEN_HOME_BUILDERS",
        "UPGRADE_PETS",
        "HOME_BASE_UPGRADE_PRIORITY",
        "TROOP_DEPLOY_TIME",
        "ATTACK_SLOT_RANGE",
    }
    assert cfg.OPEN_HOME_BUILDERS == 1
    assert cfg.UPGRADE_PETS is False
    assert cfg.HOME_BASE_UPGRADE_PRIORITY == [["Spell Factory", "Archer Queen"], ["Wall"]]
    assert cfg.TROOP_DEPLOY_TIME == 1.5
    assert cfg.ATTACK_SLOT_RANGE == (0, 6)

    # Mutate returned list to verify deep-copy isolation
    cfg.HOME_BASE_UPGRADE_PRIORITY.append(["Mortar"])

    # Switch to th16: th9 overrides must be reset to global defaults
    config_manager.apply_instance_configs("th16", cfg=cfg)
    assert cfg.OPEN_HOME_BUILDERS == 0
    assert cfg.UPGRADE_PETS is True
    assert cfg.HOME_BASE_UPGRADE_PRIORITY == [["Laboratory", "Barbarian King"], ["Wall"]]
    assert cfg.TROOP_DEPLOY_TIME == 2
    assert cfg.ATTACK_SLOT_RANGE == (0, 100)
    assert cfg.PET_HOUSE_UPGRADE_PRIORITY == [["Spirit Fox", "Angry Jelly"]]

    # Switch to main (no overrides): everything back to global defaults
    config_manager.apply_instance_configs("main", cfg=cfg)
    assert cfg.PET_HOUSE_UPGRADE_PRIORITY == [["Unicorn", "Phoenix"]]
    assert cfg.OPEN_HOME_BUILDERS == 0


def test_get_instance_config_does_not_mutate_global():
    cfg = _make_fake_configs(
        INSTANCE_CONFIGS={
            "th9": {"UPGRADE_PETS": False, "HOME_BASE_UPGRADE_PRIORITY": [["Barracks"]]},
        }
    )

    assert config_manager.get_instance_config("th9", "UPGRADE_PETS", cfg=cfg) is False
    assert config_manager.get_instance_config("main", "UPGRADE_PETS", cfg=cfg) is True
    assert config_manager.get_instance_config("th9", "HOME_BASE_UPGRADE_PRIORITY", cfg=cfg) == [["Barracks"]]
    # Global module remains untouched
    assert cfg.UPGRADE_PETS is True
    assert cfg.HOME_BASE_UPGRADE_PRIORITY == [["Laboratory", "Barbarian King"], ["Wall"]]


def test_get_resolved_configs_merges_base_and_overrides():
    cfg = _make_fake_configs(
        INSTANCE_CONFIGS={
            "th9": {"CHECK_INTERVAL": 15, "ATTACK_HOME_BASE": False},
        }
    )
    resolved = config_manager.get_resolved_configs("th9", cfg=cfg)
    assert resolved["CHECK_INTERVAL"] == 15
    assert resolved["ATTACK_HOME_BASE"] is False
    assert resolved["UPGRADE_HOME_BASE"] is True


def test_validation_rejects_unknown_key():
    cfg = _make_fake_configs(
        INSTANCE_CONFIGS={"th9": {"OPEN_HOME_BUILDER": 1}}  # typo
    )
    with pytest.raises(ValueError, match="Unknown config key 'OPEN_HOME_BUILDER'"):
        config_manager.apply_instance_configs("th9", cfg=cfg)


def test_validation_rejects_non_overridable_keys():
    for forbidden in ("INSTANCE_IDS", "DEFAULT_INSTANCE_ID", "INSTANCE_CONFIGS"):
        cfg = _make_fake_configs(INSTANCE_CONFIGS={"th9": {forbidden: []}})
        with pytest.raises(ValueError, match="cannot be overridden per instance"):
            config_manager.apply_instance_configs("th9", cfg=cfg)


def test_validation_rejects_invalid_container_types():
    cfg_bad_root = _make_fake_configs(INSTANCE_CONFIGS=["not", "a", "dict"])
    with pytest.raises(ValueError, match="must be a dict"):
        config_manager.validate_instance_configs(cfg=cfg_bad_root)

    cfg_bad_entry = _make_fake_configs(INSTANCE_CONFIGS={"th9": "invalid"})
    with pytest.raises(ValueError, match="must be a dict of config overrides"):
        config_manager.validate_instance_configs(cfg=cfg_bad_entry)


def test_unknown_instance_id_logs_warning_without_crashing():
    warnings = []

    class FakeLogger:
        def warning(self, msg):
            warnings.append(msg)

        def info(self, msg):
            pass

    cfg = _make_fake_configs(
        INSTANCE_CONFIGS={"inactive_alt": {"OPEN_HOME_BUILDERS": 2}}
    )
    config_manager.apply_instance_configs("main", cfg=cfg, logger=FakeLogger())
    assert any("inactive_alt" in w for w in warnings)
