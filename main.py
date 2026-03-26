"""桌面待办小应用 - 程序入口"""

import sys
import os
import traceback
from pathlib import Path
from datetime import datetime

# 高 DPI 适配
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

# 将项目根目录加入 sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from src.utils.paths import get_user_data_root

# 本地 socket 名称，用于单实例检测与唤醒
_SERVER_NAME = "DesktopTodo_SingleInstance"


def _get_crash_log_path():
    """获取崩溃日志路径"""
    return get_user_data_root() / "crash.log"


def _global_exception_handler(exc_type, exc_value, exc_tb):
    """全局异常处理器，将未捕获异常写入 crash.log 并弹窗提示"""
    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n{'='*60}\n[{timestamp}]\n{tb_text}\n"
    try:
        log_path = _get_crash_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception:
        pass
    try:
        QMessageBox.critical(
            None, "桌面待办 - 错误",
            f"程序遇到错误，已记录到 crash.log:\n\n{exc_value}"
        )
    except Exception:
        pass


def _try_send_show():
    """尝试连接已运行的实例并发送唤醒信号，成功返回 True"""
    socket = QLocalSocket()
    socket.connectToServer(_SERVER_NAME)
    if socket.waitForConnected(500):
        socket.write(b"show")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True
    return False


def main():
    # 全局异常捕获
    sys.excepthook = _global_exception_handler

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 使用 Fusion 样式，完全遵从 QSS，避免 Windows 原生样式覆盖深色主题输入框颜色

    # 单实例检测：尝试连接已有实例
    if _try_send_show():
        sys.exit(0)

    # 启动本地服务器，监听后续实例的唤醒请求
    server = QLocalServer()
    # 清理可能残留的 socket（如上次崩溃后未清理）
    QLocalServer.removeServer(_SERVER_NAME)
    server.listen(_SERVER_NAME)

    from src.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    # 当新连接到达时，唤醒窗口
    def _on_new_connection():
        conn = server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(500)
            conn.close()
        window.bring_to_front()

    server.newConnection.connect(_on_new_connection)

    ret = app.exec_()
    server.close()
    sys.exit(ret)


if __name__ == "__main__":
    main()
