"""
配置加载器 - 从 YAML 文件加载配置，支持环境变量覆盖
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


DEFAULT_CONFIG_PATH = "config/config.yaml"
LOCAL_CONFIG_PATH = "config/local_config.yaml"


def _deep_merge(base: Dict, override: Dict) -> Dict:
    """深度合并两个字典，override 覆盖 base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    加载配置，优先级：
    1. 命令行指定的配置文件
    2. local_config.yaml（用户自定义，含敏感信息）
    3. config.yaml（默认模板）
    """
    # 加载默认配置
    default_file = Path(DEFAULT_CONFIG_PATH)
    config = {}
    if default_file.exists():
        with open(default_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

    # 加载本地配置（覆盖默认）
    local_file = Path(LOCAL_CONFIG_PATH)
    if local_file.exists():
        with open(local_file, "r", encoding="utf-8") as f:
            local_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, local_config)

    # 加载命令行指定的配置（最高优先级）
    if config_path:
        custom_file = Path(config_path)
        if custom_file.exists():
            with open(custom_file, "r", encoding="utf-8") as f:
                custom_config = yaml.safe_load(f) or {}
            config = _deep_merge(config, custom_config)

    # 环境变量覆盖（TCG_ 前缀）
    env_overrides = {}
    for key, value in os.environ.items():
        if key.startswith("TCG_"):
            # TCG_KB_API_URL → kb_api.url
            parts = key[4:].lower().split("__")
            if len(parts) >= 2:
                d = env_overrides
                for p in parts[:-1]:
                    d.setdefault(p, {})
                    d = d[p]
                d[parts[-1]] = value
    if env_overrides:
        config = _deep_merge(config, env_overrides)

    return config


def get_config_value(config: Dict, path: str, default: Any = None) -> Any:
    """
    按路径获取配置值
    例: get_config_value(config, "kb_api.url") → config["kb_api"]["url"]
    """
    keys = path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value
