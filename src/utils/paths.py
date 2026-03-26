"""路径工具 - 统一处理开发环境与 PyInstaller 打包后的路径"""

import os
import sys
from pathlib import Path


def get_app_root() -> Path:
    """
    获取应用根目录。
    - 开发环境：项目根目录（main.py 所在目录）
    - PyInstaller 打包后：exe 所在目录
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent.parent.parent


def get_user_data_root() -> Path:
    """
    获取用户数据根目录（数据库、配置文件等）。
    - 开发环境：项目根目录
    - PyInstaller 打包后：
        - Windows: %LOCALAPPDATA%/桌面待办/
        - macOS:   ~/Library/Application Support/桌面待办/
        - Linux:   ~/.local/share/桌面待办/
    """
    if getattr(sys, 'frozen', False):
        if sys.platform == "win32":
            local_app = os.environ.get("LOCALAPPDATA")
            if local_app:
                return Path(local_app) / "桌面待办"
        elif sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "桌面待办"
        else:
            return Path.home() / ".local" / "share" / "桌面待办"
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent.parent.parent


def get_data_dir() -> Path:
    """获取数据目录（data/）"""
    d = get_user_data_root() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_config_path() -> Path:
    """获取配置文件路径（config.json）"""
    p = get_user_data_root()
    p.mkdir(parents=True, exist_ok=True)
    return p / "config.json"
