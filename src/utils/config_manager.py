"""配置文件管理器 - 读写 config.json"""

import json
import copy
from pathlib import Path
from typing import Any, Optional
from src.utils.paths import get_config_path

_CONFIG_PATH = get_config_path()

# 默认配置
DEFAULT_CONFIG = {
    "window": {
        "x": 100,
        "y": 100,
        "width": 320,
        "height": 600,
        "opacity": 0.95,
        "always_on_top": True,
    },
    "theme": {
        "mode": "semi_transparent",    # 'semi_transparent' | 'solid'
        "primary_color": "#6366F1",
        "background_color": "#1E1E2E",
    },
    "behavior": {
        "start_with_windows": False,
        "minimize_to_tray": True,
    },
    "current_filter": {
        "type": "smart_list",          # 'smart_list' | 'tag'
        "value": "today",             # 'today' | 'week' | 'overdue' | tag_id
    },
}


class ConfigManager:
    """管理 config.json 的读写操作"""

    def __init__(self, config_path: Optional[Path] = None):
        self._path = config_path or _CONFIG_PATH
        self._config: dict = {}
        self._load()

    def _load(self):
        """从文件加载配置，文件不存在则使用默认配置并写入"""
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
                # 合并缺失的默认键
                self._config = self._merge_defaults(DEFAULT_CONFIG, self._config)
            except (json.JSONDecodeError, IOError):
                self._config = copy.deepcopy(DEFAULT_CONFIG)
                self._save()
        else:
            self._config = copy.deepcopy(DEFAULT_CONFIG)
            self._save()

    def _merge_defaults(self, defaults: dict, current: dict) -> dict:
        """递归合并：current 中缺失的键用 defaults 补齐"""
        merged = copy.deepcopy(defaults)
        for key, value in current.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_defaults(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _save(self):
        """将配置写入 config.json"""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=4)
        except (IOError, OSError, PermissionError):
            pass

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        通过点分路径获取配置值。
        示例: config.get("window.opacity") -> 0.95
        """
        keys = key_path.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key_path: str, value: Any):
        """
        通过点分路径设置配置值并自动保存。
        示例: config.set("window.opacity", 0.8)
        """
        keys = key_path.split(".")
        target = self._config
        for k in keys[:-1]:
            if k not in target or not isinstance(target[k], dict):
                target[k] = {}
            target = target[k]
        target[keys[-1]] = value
        self._save()

    def get_all(self) -> dict:
        """返回完整配置字典的副本"""
        return self._config.copy()

    def reset(self):
        """重置为默认配置"""
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        self._save()
