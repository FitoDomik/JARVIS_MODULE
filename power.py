import sys
import os
import time
import threading
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QComboBox, 
                           QSpinBox, QTabWidget, QGridLayout, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QIcon
class SleepWorker(QThread):
    finished = pyqtSignal()
    progress = pyqtSignal(int)
    def __init__(self, seconds):
        super().__init__()
        self.seconds = seconds
        self.is_running = True
    def run(self):
        for i in range(self.seconds, 0, -1):
            if not self.is_running:
                break
            self.progress.emit(i)
            time.sleep(1)
        if self.is_running:
            self.finished.emit()
    def stop(self):
        self.is_running = False
class PowerManager:
    @staticmethod
    def sleep():
        if sys.platform == 'win32':
            os.system('rundll32.exe powrprof.dll,SetSuspendState 0,1,0')
        elif sys.platform == 'darwin':  
            os.system('pmset sleepnow')
        else:  
            os.system('systemctl suspend')
    @staticmethod
    def hibernate():
        if sys.platform == 'win32':
            os.system('rundll32.exe powrprof.dll,SetSuspendState 1,1,0')
        elif sys.platform == 'darwin':  
            os.system('pmset hibernatenow')
        else:  
            os.system('systemctl hibernate')
    @staticmethod
    def shutdown():
        if sys.platform == 'win32':
            os.system('shutdown /s /t 0')
        elif sys.platform == 'darwin':  
            os.system('shutdown -h now')
        else:  
            os.system('shutdown now')
    @staticmethod
    def restart():
        if sys.platform == 'win32':
            os.system('shutdown /r /t 0')
        elif sys.platform == 'darwin':  
            os.system('shutdown -r now')
        else:  
            os.system('reboot')
class PowerControlApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Управление питанием")
        self.setMinimumSize(500, 400)
        self.sleep_worker = None
        self.remaining_time = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_timer_display)
        self.init_ui()
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        quick_actions_tab = QWidget()
        quick_layout = QVBoxLayout(quick_actions_tab)
        title_label = QLabel("Быстрые действия")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        quick_layout.addWidget(title_label)
        buttons_layout = QGridLayout()
        quick_layout.addLayout(buttons_layout)
        sleep_btn = QPushButton("Спящий режим")
        sleep_btn.setMinimumHeight(60)
        sleep_btn.clicked.connect(self.activate_sleep)
        buttons_layout.addWidget(sleep_btn, 0, 0)
        hibernate_btn = QPushButton("Гибернация")
        hibernate_btn.setMinimumHeight(60)
        hibernate_btn.clicked.connect(self.activate_hibernate)
        buttons_layout.addWidget(hibernate_btn, 0, 1)
        shutdown_btn = QPushButton("Выключение")
        shutdown_btn.setMinimumHeight(60)
        shutdown_btn.clicked.connect(self.activate_shutdown)
        buttons_layout.addWidget(shutdown_btn, 1, 0)
        restart_btn = QPushButton("Перезагрузка")
        restart_btn.setMinimumHeight(60)
        restart_btn.clicked.connect(self.activate_restart)
        buttons_layout.addWidget(restart_btn, 1, 1)
        tabs.addTab(quick_actions_tab, "Быстрые действия")
        timer_tab = QWidget()
        timer_layout = QVBoxLayout(timer_tab)
        timer_title = QLabel("Таймер спящего режима")
        timer_title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        timer_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(timer_title)
        time_selection_layout = QHBoxLayout()
        timer_layout.addLayout(time_selection_layout)
        time_label = QLabel("Установить таймер на:")
        time_label.setFont(QFont("Arial", 12))
        time_selection_layout.addWidget(time_label)
        self.time_unit = QComboBox()
        self.time_unit.addItems(["секунд", "минут", "часов"])
        time_selection_layout.addWidget(self.time_unit)
        self.time_value = QSpinBox()
        self.time_value.setRange(1, 999)
        self.time_value.setValue(30)
        self.time_value.setMinimumWidth(80)
        time_selection_layout.addWidget(self.time_value)
        timer_buttons_layout = QHBoxLayout()
        timer_layout.addLayout(timer_buttons_layout)
        self.start_timer_btn = QPushButton("Запустить таймер")
        self.start_timer_btn.setMinimumHeight(50)
        self.start_timer_btn.clicked.connect(self.start_timer)
        timer_buttons_layout.addWidget(self.start_timer_btn)
        self.stop_timer_btn = QPushButton("Остановить таймер")
        self.stop_timer_btn.setMinimumHeight(50)
        self.stop_timer_btn.setEnabled(False)
        self.stop_timer_btn.clicked.connect(self.stop_timer)
        timer_buttons_layout.addWidget(self.stop_timer_btn)
        self.time_display_layout = QVBoxLayout()
        timer_layout.addLayout(self.time_display_layout)
        self.time_display = QLabel("Таймер не активен")
        self.time_display.setFont(QFont("Arial", 14))
        self.time_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_display_layout.addWidget(self.time_display)
        action_layout = QHBoxLayout()
        timer_layout.addLayout(action_layout)
        action_label = QLabel("Действие по таймеру:")
        action_label.setFont(QFont("Arial", 12))
        action_layout.addWidget(action_label)
        self.action_selector = QComboBox()
        self.action_selector.addItems(["Спящий режим", "Гибернация", "Выключение", "Перезагрузка"])
        action_layout.addWidget(self.action_selector)
        tabs.addTab(timer_tab, "Таймер")
    def activate_sleep(self):
        self.confirm_action("Спящий режим", PowerManager.sleep)
    def activate_hibernate(self):
        self.confirm_action("Гибернация", PowerManager.hibernate)
    def activate_shutdown(self):
        self.confirm_action("Выключение", PowerManager.shutdown)
    def activate_restart(self):
        self.confirm_action("Перезагрузка", PowerManager.restart)
    def confirm_action(self, action_name, action_function):
        reply = QMessageBox.question(
            self, 
            f"Подтверждение действия: {action_name}", 
            f"Вы уверены, что хотите выполнить действие: {action_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            action_function()
    def start_timer(self):
        value = self.time_value.value()
        unit = self.time_unit.currentText()
        seconds = 0
        if unit == "секунд":
            seconds = value
        elif unit == "минут":
            seconds = value * 60
        else:  
            seconds = value * 3600
        if self.sleep_worker is not None:
            self.sleep_worker.stop()
            self.sleep_worker.wait()
        self.sleep_worker = SleepWorker(seconds)
        self.sleep_worker.progress.connect(self.update_progress)
        self.sleep_worker.finished.connect(self.timer_finished)
        self.sleep_worker.start()
        self.start_timer_btn.setEnabled(False)
        self.stop_timer_btn.setEnabled(True)
        self.time_value.setEnabled(False)
        self.time_unit.setEnabled(False)
        self.action_selector.setEnabled(False)
        self.remaining_time = seconds
        self.timer.start(1000)
    def stop_timer(self):
        if self.sleep_worker is not None:
            self.sleep_worker.stop()
            self.sleep_worker.wait()
            self.sleep_worker = None
        self.timer.stop()
        self.time_display.setText("Таймер остановлен")
        self.start_timer_btn.setEnabled(True)
        self.stop_timer_btn.setEnabled(False)
        self.time_value.setEnabled(True)
        self.time_unit.setEnabled(True)
        self.action_selector.setEnabled(True)
    def update_progress(self, seconds):
        self.remaining_time = seconds
    def update_timer_display(self):
        hours, remainder = divmod(self.remaining_time, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"{hours:02}:{minutes:02}:{seconds:02}"
        self.time_display.setText(f"Осталось: {time_str}")
    def timer_finished(self):
        self.timer.stop()
        action = self.action_selector.currentText()
        if action == "Спящий режим":
            PowerManager.sleep()
        elif action == "Гибернация":
            PowerManager.hibernate()
        elif action == "Выключение":
            PowerManager.shutdown()
        elif action == "Перезагрузка":
            PowerManager.restart()
        self.time_display.setText("Таймер завершен")
        self.start_timer_btn.setEnabled(True)
        self.stop_timer_btn.setEnabled(False)
        self.time_value.setEnabled(True)
        self.time_unit.setEnabled(True)
        self.action_selector.setEnabled(True)
    def closeEvent(self, event):
        if self.sleep_worker is not None and self.sleep_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Подтверждение выхода",
                "Таймер активен. Вы уверены, что хотите выйти?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_timer()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  
    window = PowerControlApp()
    window.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main() 