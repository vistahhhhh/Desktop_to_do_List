"""第五阶段测试 - 设置面板、系统托盘、窗口置顶、位置记忆"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.ui.settings_panel import SettingsPanel
from src.ui.system_tray import SystemTray, _create_tray_icon
from src.ui.styles.themes import get_theme_keys, get_theme, build_stylesheet

app = QApplication.instance() or QApplication(sys.argv)


# ============================================================
# 1. SettingsPanel 测试
# ============================================================
def test_settings_panel_creation():
    panel = SettingsPanel("dark", 0.95, True)
    assert panel.windowTitle() == "设置"
    assert panel.theme_combo.currentData() == "dark"
    assert panel.opacity_slider.value() == 95
    assert panel.top_check.isChecked() is True
    print("[PASS] test_settings_panel_creation - 设置面板创建正确")


def test_settings_panel_different_initial():
    panel = SettingsPanel("light", 0.6, False)
    assert panel.theme_combo.currentData() == "light"
    assert panel.opacity_slider.value() == 60
    assert panel.top_check.isChecked() is False
    assert panel.opacity_value_label.text() == "60%"
    print("[PASS] test_settings_panel_different_initial - 不同初始值加载正确")


def test_settings_theme_signal():
    panel = SettingsPanel("dark", 0.95, True)
    received = []
    panel.theme_changed.connect(lambda key: received.append(key))

    # 切换到 light (index 1)
    keys = get_theme_keys()
    light_idx = keys.index("light")
    panel.theme_combo.setCurrentIndex(light_idx)

    assert len(received) == 1
    assert received[0] == "light"
    print("[PASS] test_settings_theme_signal - 主题切换信号正确")


def test_settings_opacity_signal():
    panel = SettingsPanel("dark", 0.95, True)
    received = []
    panel.opacity_changed.connect(lambda v: received.append(v))

    panel.opacity_slider.setValue(70)
    assert len(received) >= 1
    assert abs(received[-1] - 0.7) < 0.01
    assert panel.opacity_value_label.text() == "70%"
    print("[PASS] test_settings_opacity_signal - 透明度信号正确")


def test_settings_opacity_range():
    panel = SettingsPanel("dark", 0.95, True)
    assert panel.opacity_slider.minimum() == 30
    assert panel.opacity_slider.maximum() == 100
    print("[PASS] test_settings_opacity_range - 透明度范围 30-100")


def test_settings_top_signal():
    panel = SettingsPanel("dark", 0.95, True)
    received = []
    panel.always_on_top_changed.connect(lambda v: received.append(v))

    panel.top_check.setChecked(False)
    assert len(received) == 1
    assert received[0] is False

    panel.top_check.setChecked(True)
    assert len(received) == 2
    assert received[1] is True
    print("[PASS] test_settings_top_signal - 置顶开关信号正确")


def test_settings_all_themes_listed():
    panel = SettingsPanel("dark", 0.95, True)
    keys = get_theme_keys()
    assert panel.theme_combo.count() == len(keys)
    for i in range(panel.theme_combo.count()):
        assert panel.theme_combo.itemData(i) in keys
    print("[PASS] test_settings_all_themes_listed - 所有主题都在下拉框中")


# ============================================================
# 2. SystemTray 测试
# ============================================================
def test_tray_icon_creation():
    icon = _create_tray_icon()
    assert not icon.isNull()
    print("[PASS] test_tray_icon_creation - 托盘图标生成正确")


def test_tray_signals():
    tray = SystemTray()
    received = {"show": 0, "quit": 0, "settings": 0, "add": 0}
    tray.show_requested.connect(lambda: received.__setitem__("show", received["show"] + 1))
    tray.quit_requested.connect(lambda: received.__setitem__("quit", received["quit"] + 1))
    tray.settings_requested.connect(lambda: received.__setitem__("settings", received["settings"] + 1))
    tray.add_task_requested.connect(lambda: received.__setitem__("add", received["add"] + 1))

    # 手动发射信号
    tray.show_requested.emit()
    tray.quit_requested.emit()
    tray.settings_requested.emit()
    tray.add_task_requested.emit()

    assert received["show"] == 1
    assert received["quit"] == 1
    assert received["settings"] == 1
    assert received["add"] == 1
    print("[PASS] test_tray_signals - 托盘信号正确")


def test_tray_visibility():
    tray = SystemTray()
    tray.show()
    assert tray.is_visible()
    tray.hide()
    assert not tray.is_visible()
    print("[PASS] test_tray_visibility - 托盘显隐正确")


def test_tray_menu_exists():
    tray = SystemTray()
    menu = tray.tray_icon.contextMenu()
    assert menu is not None
    # 应有 4 个 action (显示、新建、设置、退出) + 1 separator
    actions = menu.actions()
    assert len(actions) >= 4
    print("[PASS] test_tray_menu_exists - 托盘菜单存在")


def test_tray_tooltip():
    tray = SystemTray()
    assert tray.tray_icon.toolTip() == "桌面待办"
    print("[PASS] test_tray_tooltip - 托盘提示文字正确")


# ============================================================
# 3. QSS 样式测试
# ============================================================
def test_settings_styles_in_theme():
    for key in get_theme_keys():
        theme = get_theme(key)
        qss = build_stylesheet(theme)
        assert "SettingsLabel" in qss
        assert "SettingsCombo" in qss
        assert "SettingsSlider" in qss
        assert "SettingsCheck" in qss
        assert "SettingsSeparator" in qss
    print("[PASS] test_settings_styles_in_theme - 设置面板样式存在于主题中")


# ============================================================
# 4. 位置记忆测试（ConfigManager 集成）
# ============================================================
def test_position_config_persistence():
    import tempfile, json
    from src.utils.config_manager import ConfigManager

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        f.write("{}")
        tmp_path = Path(f.name)

    try:
        cfg = ConfigManager(config_path=tmp_path)
        cfg.set("window.x", 200)
        cfg.set("window.y", 300)
        cfg.set("window.width", 400)
        cfg.set("window.height", 700)
        cfg.set("window.opacity", 0.8)
        cfg.set("window.always_on_top", False)
        cfg.set("theme.mode", "morandy")

        # 重新加载
        cfg2 = ConfigManager(config_path=tmp_path)
        assert cfg2.get("window.x") == 200
        assert cfg2.get("window.y") == 300
        assert cfg2.get("window.width") == 400
        assert cfg2.get("window.height") == 700
        assert abs(cfg2.get("window.opacity") - 0.8) < 0.01
        assert cfg2.get("window.always_on_top") is False
        assert cfg2.get("theme.mode") == "morandy"
    finally:
        tmp_path.unlink(missing_ok=True)

    print("[PASS] test_position_config_persistence - 位置/设置配置持久化正确")


def test_config_defaults_for_new_keys():
    import tempfile, os, json
    from src.utils.config_manager import ConfigManager

    tmp_path = Path(tempfile.mktemp(suffix=".json"))
    tmp_path.write_text("{}", encoding="utf-8")

    try:
        cfg = ConfigManager(config_path=tmp_path)
        val = cfg.get("window.always_on_top")
        assert val == True, f"expected True, got {val!r} ({type(val)})"
        val2 = cfg.get("behavior.minimize_to_tray")
        assert val2 == True, f"expected True, got {val2!r} ({type(val2)})"
    finally:
        tmp_path.unlink(missing_ok=True)

    print("[PASS] test_config_defaults_for_new_keys - 新配置键有默认值")


# ============================================================
# 运行所有测试
# ============================================================
def run_all():
    tests = [
        # 设置面板
        test_settings_panel_creation,
        test_settings_panel_different_initial,
        test_settings_theme_signal,
        test_settings_opacity_signal,
        test_settings_opacity_range,
        test_settings_top_signal,
        test_settings_all_themes_listed,
        # 系统托盘
        test_tray_icon_creation,
        test_tray_signals,
        test_tray_visibility,
        test_tray_menu_exists,
        test_tray_tooltip,
        # 样式
        test_settings_styles_in_theme,
        # 配置持久化
        test_position_config_persistence,
        test_config_defaults_for_new_keys,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*50}")
    print(f"测试结果: {passed} 通过, {failed} 失败, 共 {len(tests)} 项")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
