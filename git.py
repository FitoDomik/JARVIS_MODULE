import sys
import json
import time
import threading
import random
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QLabel, QLineEdit, QPushButton, QListWidget, 
    QListWidgetItem, QTextEdit, QSpinBox, QComboBox, QMessageBox,
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter, QInputDialog,
    QMenu
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
import pynput
from pynput import keyboard, mouse
from pynput.keyboard import Key, Listener as KeyboardListener
from pynput.mouse import Button, Listener as MouseListener
@dataclass
class MacroAction:
    type: str  
    key: Optional[str] = None
    second_key: Optional[str] = None  
    button: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    delay: float = 0.0
    is_loop_start: bool = False
    is_loop_end: bool = False
    loop_count: int = 1
    random_delay_min: float = 0.0
    random_delay_max: float = 0.0
    use_random_delay: bool = False
    use_micro_movements: bool = False
    simplified_display: bool = True  
@dataclass
class Macro:
    name: str
    actions: List[MacroAction]
    hotkey: str = ""
    enabled: bool = True
    created_at: str = ""
    anti_detect_mode: bool = False
    random_delay_percent: int = 20
    micro_movement_radius: int = 5
    simplified_display: bool = True  
    voice_command: str = ""  
class MacroRecorder(QObject):
    action_recorded = pyqtSignal(MacroAction)
    recording_finished = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.recording = False
        self.actions = []
        self.last_action_time = 0
        self.keyboard_listener = None
        self.mouse_listener = None
        self.pressed_keys = set()  
        self.simplified_display = True  
        self.anti_detect_mode = False
        self.random_delay_percent = 20
        self.micro_movement_radius = 5
    def start_recording(self, simplified_display=True):
        self.recording = True
        self.actions = []
        self.last_action_time = time.time()
        self.pressed_keys.clear()
        self.simplified_display = simplified_display
        self.keyboard_listener = KeyboardListener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.mouse_listener = MouseListener(
            on_click=self._on_mouse_click,
            on_move=self._on_mouse_move
        )
        self.keyboard_listener.start()
        self.mouse_listener.start()
    def stop_recording(self):
        self.recording = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()
        self.recording_finished.emit()
    def _calculate_delay(self):
        current_time = time.time()
        delay = current_time - self.last_action_time
        self.last_action_time = current_time
        return delay
    def _on_key_press(self, key):
        if not self.recording:
            return
        delay = self._calculate_delay()
        key_str = str(key).replace("'", "")
        second_key = None
        if self.pressed_keys and self.simplified_display:
            for pressed_key in self.pressed_keys:
                if pressed_key != key_str:
                    second_key = pressed_key
                    break
        self.pressed_keys.add(key_str)
        action = MacroAction(
            type='key_press',
            key=key_str,
            second_key=second_key,
            delay=delay,
            simplified_display=self.simplified_display
        )
        self.actions.append(action)
        self.action_recorded.emit(action)
    def _on_key_release(self, key):
        if not self.recording:
            return
        if key == Key.esc:
            self.stop_recording()
            return
        key_str = str(key).replace("'", "")
        if key_str in self.pressed_keys:
            self.pressed_keys.remove(key_str)
        if self.simplified_display:
            return
        delay = self._calculate_delay()
        action = MacroAction(
            type='key_release',
            key=key_str,
            delay=delay,
            simplified_display=self.simplified_display
        )
        self.actions.append(action)
        self.action_recorded.emit(action)
    def _on_mouse_click(self, x, y, button, pressed):
        if not self.recording:
            return
        delay = self._calculate_delay()
        if self.simplified_display and not pressed:
            return
        action = MacroAction(
            type='mouse_click' if pressed else 'mouse_release',
            button=str(button),
            x=x,
            y=y,
            delay=delay,
            simplified_display=self.simplified_display
        )
        self.actions.append(action)
        self.action_recorded.emit(action)
    def _on_mouse_move(self, x, y):
        if not self.recording:
            return
        if len(self.actions) == 0 or not (
            hasattr(self.actions[-1], 'x') and 
            abs(self.actions[-1].x - x) < 5 and 
            abs(self.actions[-1].y - y) < 5
        ):
            delay = self._calculate_delay()
            action = MacroAction(
                type='mouse_move',
                x=x,
                y=y,
                delay=delay,
                simplified_display=self.simplified_display
            )
            self.actions.append(action)
            self.action_recorded.emit(action)
class MacroPlayer:
    def __init__(self):
        self.keyboard_controller = pynput.keyboard.Controller()
        self.mouse_controller = pynput.mouse.Controller()
        self.stop_requested = False
        self.current_loop_stack = []  
    def play_macro(self, macro: Macro):
        if not macro.enabled:
            return
        def play_thread():
            self.stop_requested = False
            self.current_loop_stack = []
            i = 0
            while i < len(macro.actions) and not self.stop_requested:
                action = macro.actions[i]
                if action.is_loop_start:
                    loop_info = {
                        'start_index': i,
                        'count': action.loop_count,
                        'iterations_done': 0
                    }
                    self.current_loop_stack.append(loop_info)
                    i += 1
                    continue
                elif action.is_loop_end and self.current_loop_stack:
                    current_loop = self.current_loop_stack[-1]
                    current_loop['iterations_done'] += 1
                    if current_loop['iterations_done'] < current_loop['count']:
                        i = current_loop['start_index'] + 1
                    else:
                        self.current_loop_stack.pop()
                        i += 1
                    continue
                try:
                    delay = self._calculate_delay(action, macro.anti_detect_mode, macro.random_delay_percent)
                    if delay > 0:
                        time.sleep(min(delay, 10.0))  
                    if action.type == 'key_press':
                        if action.second_key:
                            self._press_key(action.second_key)
                            self._press_key(action.key)
                            time.sleep(0.05)
                            self._release_key(action.key)
                            self._release_key(action.second_key)
                        else:
                            self._press_key(action.key)
                            if action.simplified_display:
                                time.sleep(0.05)  
                                self._release_key(action.key)
                    elif action.type == 'key_release' and not action.simplified_display:
                        self._release_key(action.key)
                    elif action.type == 'mouse_click':
                        self._click_mouse(action, macro.anti_detect_mode, macro.micro_movement_radius)
                    elif action.type == 'mouse_move':
                        self._move_mouse(action, macro.anti_detect_mode, macro.micro_movement_radius)
                except Exception as e:
                    print(f"Ошибка при воспроизведении действия: {e}")
                i += 1
        thread = threading.Thread(target=play_thread)
        thread.daemon = True
        thread.start()
    def stop_playback(self):
        self.stop_requested = True
    def _calculate_delay(self, action: MacroAction, anti_detect_mode: bool, random_percent: int) -> float:
        delay = action.delay
        if anti_detect_mode and (action.use_random_delay or random_percent > 0):
            if action.use_random_delay and action.random_delay_min > 0 and action.random_delay_max > action.random_delay_min:
                delay = random.uniform(action.random_delay_min, action.random_delay_max)
            else:
                variation = delay * (random_percent / 100.0)
                min_delay = max(0, delay - variation)
                max_delay = delay + variation
                delay = random.uniform(min_delay, max_delay)
        return delay
    def _press_key(self, key_str: str):
        try:
            if key_str.startswith('Key.'):
                key = getattr(Key, key_str[4:])
            else:
                key = key_str
            self.keyboard_controller.press(key)
        except:
            pass
    def _release_key(self, key_str: str):
        try:
            if key_str.startswith('Key.'):
                key = getattr(Key, key_str[4:])
            else:
                key = key_str
            self.keyboard_controller.release(key)
        except:
            pass
    def _click_mouse(self, action: MacroAction, anti_detect_mode: bool, micro_movement_radius: int):
        try:
            x, y = action.x, action.y
            if x is not None and y is not None:
                if anti_detect_mode and (action.use_micro_movements or micro_movement_radius > 0):
                    radius = action.micro_movement_radius if action.use_micro_movements else micro_movement_radius
                    offset_x = random.randint(-radius, radius)
                    offset_y = random.randint(-radius, radius)
                    self.mouse_controller.position = (x + offset_x, y + offset_y)
                    time.sleep(random.uniform(0.01, 0.1))  
                    self.mouse_controller.position = (x, y)
                else:
                    self.mouse_controller.position = (x, y)
            if 'left' in action.button.lower():
                button = Button.left
            elif 'right' in action.button.lower():
                button = Button.right
            else:
                button = Button.left
            self.mouse_controller.click(button)
        except Exception as e:
            print(f"Ошибка при клике мыши: {e}")
    def _move_mouse(self, action: MacroAction, anti_detect_mode: bool, micro_movement_radius: int):
        try:
            x, y = action.x, action.y
            if x is not None and y is not None:
                if anti_detect_mode and (action.use_micro_movements or micro_movement_radius > 0):
                    current_x, current_y = self.mouse_controller.position
                    distance = ((x - current_x) ** 2 + (y - current_y) ** 2) ** 0.5
                    steps = min(max(int(distance / 10), 5), 20)  
                    for step in range(1, steps + 1):
                        progress = step / steps
                        step_x = current_x + (x - current_x) * progress
                        step_y = current_y + (y - current_y) * progress
                        radius = micro_movement_radius * (1 - progress)
                        offset_x = random.uniform(-radius, radius)
                        offset_y = random.uniform(-radius, radius)
                        self.mouse_controller.position = (step_x + offset_x, step_y + offset_y)
                        time.sleep(random.uniform(0.005, 0.02))
                    self.mouse_controller.position = (x, y)
                else:
                    self.mouse_controller.position = (x, y)
        except Exception as e:
            print(f"Ошибка при перемещении мыши: {e}")
class AutoClicker(QThread):
    def __init__(self):
        super().__init__()
        self.running = False
        self.clicks_per_minute = 60
        self.button_type = 'left'
        self.mouse_controller = pynput.mouse.Controller()
        self.anti_detect_mode = False
        self.random_delay_percent = 20
        self.micro_movement_radius = 5
    def set_clicks_per_minute(self, cpm: int):
        self.clicks_per_minute = max(1, min(cpm, 10000))
    def set_button_type(self, button_type: str):
        self.button_type = button_type
    def set_anti_detect_mode(self, enabled: bool):
        self.anti_detect_mode = enabled
    def set_random_delay_percent(self, percent: int):
        self.random_delay_percent = max(0, min(percent, 100))
    def set_micro_movement_radius(self, radius: int):
        self.micro_movement_radius = max(0, min(radius, 20))
    def start_clicking(self):
        self.running = True
        self.start()
    def stop_clicking(self):
        self.running = False
    def run(self):
        base_interval = 60.0 / self.clicks_per_minute
        while self.running:
            try:
                if self.anti_detect_mode and self.random_delay_percent > 0:
                    variation = base_interval * (self.random_delay_percent / 100.0)
                    min_interval = max(0.001, base_interval - variation)
                    max_interval = base_interval + variation
                    interval = random.uniform(min_interval, max_interval)
                else:
                    interval = base_interval
                button = Button.left if self.button_type == 'left' else Button.right
                if self.anti_detect_mode and self.micro_movement_radius > 0:
                    current_x, current_y = self.mouse_controller.position
                    offset_x = random.randint(-self.micro_movement_radius, self.micro_movement_radius)
                    offset_y = random.randint(-self.micro_movement_radius, self.micro_movement_radius)
                    self.mouse_controller.position = (current_x + offset_x, current_y + offset_y)
                    time.sleep(random.uniform(0.01, 0.05))
                    self.mouse_controller.position = (current_x, current_y)
                self.mouse_controller.click(button)
                time.sleep(interval)
            except Exception as e:
                print(f"Ошибка в автокликере: {e}")
                break
class HotkeyManager:
    def __init__(self, macro_player: MacroPlayer):
        self.macro_player = macro_player
        self.active_hotkeys = {}
        self.listener = None
    def register_hotkey(self, hotkey: str, macro: Macro):
        self.active_hotkeys[hotkey] = macro
    def unregister_hotkey(self, hotkey: str):
        if hotkey in self.active_hotkeys:
            del self.active_hotkeys[hotkey]
    def start_listening(self):
        if self.listener:
            self.listener.stop()
        self.listener = KeyboardListener(on_press=self._on_hotkey_press)
        self.listener.start()
    def stop_listening(self):
        if self.listener:
            self.listener.stop()
    def _on_hotkey_press(self, key):
        key_str = str(key).replace("'", "")
        for hotkey, macro in self.active_hotkeys.items():
            if hotkey.lower() == key_str.lower():
                self.macro_player.play_macro(macro)
                break
def parse_delay_string(delay_str: str) -> float:
    if not delay_str:
        return 0.0
    delay_str = delay_str.strip().replace(" ", "")
    delay_str = delay_str.replace(",", ".")
    seconds_pattern = r"^(\d+\.?\d*)(?:s|sec|сек|с)?$"
    milliseconds_pattern = r"^(\d+\.?\d*)(?:ms|мс)$"
    match = re.match(seconds_pattern, delay_str.lower())
    if match:
        return float(match.group(1))
    match = re.match(milliseconds_pattern, delay_str.lower())
    if match:
        return float(match.group(1)) / 1000.0
    try:
        return float(delay_str)
    except ValueError:
        return 0.0
class ActionEditDialog(QDialog):
    def __init__(self, action_type=None, key=None, second_key=None, delay=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование действия")
        self.setModal(True)
        self.resize(400, 250)
        self.setup_ui()
        if action_type:
            index = self.action_type_combo.findText(action_type)
            if index >= 0:
                self.action_type_combo.setCurrentIndex(index)
        if key:
            self.key_edit.setText(key)
        if second_key:
            self.second_key_edit.setText(second_key)
        if delay:
            self.delay_edit.setText(str(delay).replace("s", ""))
    def setup_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.action_type_combo = QComboBox()
        self.action_type_combo.addItems(["key_press", "mouse_click", "mouse_move", "loop_start", "loop_end"])
        form_layout.addRow("Тип действия:", self.action_type_combo)
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Например: a, Key.space, Button.left")
        form_layout.addRow("Клавиша/кнопка:", self.key_edit)
        self.second_key_edit = QLineEdit()
        self.second_key_edit.setPlaceholderText("Для комбинаций клавиш (например: ctrl)")
        form_layout.addRow("Вторая клавиша:", self.second_key_edit)
        self.delay_edit = QLineEdit()
        self.delay_edit.setPlaceholderText("Задержка в секундах (например: 0.5)")
        self.delay_edit.setText("0.1")
        form_layout.addRow("Задержка (сек):", self.delay_edit)
        layout.addLayout(form_layout)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)
    def get_action_data(self):
        action_type = self.action_type_combo.currentText()
        key = self.key_edit.text()
        second_key = self.second_key_edit.text()
        try:
            delay = float(self.delay_edit.text())
        except ValueError:
            delay = 0.1
        return action_type, key, second_key, delay
class MacroEditDialog(QDialog):
    def __init__(self, macro: Optional[Macro] = None, parent=None):
        super().__init__(parent)
        self.macro = macro
        self.setWindowTitle("Редактировать макрос" if macro else "Создать макрос")
        self.setModal(True)
        self.resize(700, 550)
        self.setup_ui()
        if macro:
            self.load_macro_data()
    def setup_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите название макроса")
        form_layout.addRow("Название:", self.name_edit)
        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setPlaceholderText("Например: F10, ctrl+a, alt+shift")
        form_layout.addRow("Горячая клавиша:", self.hotkey_edit)
        self.enabled_check = QCheckBox("Включен")
        self.enabled_check.setChecked(True)
        form_layout.addRow("", self.enabled_check)
        self.simplified_display_check = QCheckBox("Упрощенное отображение действий")
        self.simplified_display_check.setChecked(True)
        self.simplified_display_check.setToolTip("Показывать только нажатия клавиш без отпускания")
        form_layout.addRow("", self.simplified_display_check)
        self.voice_command_edit = QLineEdit()
        self.voice_command_edit.setPlaceholderText("Например: нажми левую кнопку мыши")
        form_layout.addRow("Голосовая команда:", self.voice_command_edit)
        anti_detect_group = QGroupBox("Антидетект режим")
        anti_detect_layout = QFormLayout()
        self.anti_detect_check = QCheckBox("Включить")
        self.anti_detect_check.setToolTip("Добавляет случайные задержки и микродвижения для имитации человеческих действий")
        anti_detect_layout.addRow("", self.anti_detect_check)
        self.random_delay_spin = QSpinBox()
        self.random_delay_spin.setRange(0, 100)
        self.random_delay_spin.setValue(20)
        self.random_delay_spin.setSuffix("%")
        anti_detect_layout.addRow("Случайная задержка:", self.random_delay_spin)
        self.micro_movement_spin = QSpinBox()
        self.micro_movement_spin.setRange(0, 20)
        self.micro_movement_spin.setValue(5)
        self.micro_movement_spin.setSuffix(" пикселей")
        anti_detect_layout.addRow("Микродвижения мыши:", self.micro_movement_spin)
        anti_detect_group.setLayout(anti_detect_layout)
        form_layout.addRow("", anti_detect_group)
        layout.addLayout(form_layout)
        actions_group = QGroupBox("Действия макроса")
        actions_layout = QVBoxLayout()
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(4)  
        self.actions_table.setHorizontalHeaderLabels(["Тип", "Клавиша/Кнопка", "Вторая клавиша", "Задержка (сек)"])
        self.actions_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.actions_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.actions_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.actions_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.actions_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.actions_table.customContextMenuRequested.connect(self.show_context_menu)
        self.actions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        actions_layout.addWidget(self.actions_table)
        tools_layout = QHBoxLayout()
        self.add_loop_start_btn = QPushButton("Начало цикла")
        self.add_loop_end_btn = QPushButton("Конец цикла")
        self.add_action_btn = QPushButton("Добавить действие")
        self.edit_action_btn = QPushButton("Изменить")
        self.delete_action_btn = QPushButton("Удалить")
        self.move_up_btn = QPushButton("↑")
        self.move_down_btn = QPushButton("↓")
        tools_layout.addWidget(self.add_action_btn)
        tools_layout.addWidget(self.edit_action_btn)
        tools_layout.addWidget(self.delete_action_btn)
        tools_layout.addWidget(self.move_up_btn)
        tools_layout.addWidget(self.move_down_btn)
        tools_layout.addSpacing(20)
        tools_layout.addWidget(self.add_loop_start_btn)
        tools_layout.addWidget(self.add_loop_end_btn)
        actions_layout.addLayout(tools_layout)
        self.add_action_btn.clicked.connect(self.add_action)
        self.edit_action_btn.clicked.connect(self.edit_action)
        self.delete_action_btn.clicked.connect(self.delete_action)
        self.move_up_btn.clicked.connect(self.move_action_up)
        self.move_down_btn.clicked.connect(self.move_action_down)
        self.add_loop_start_btn.clicked.connect(self.add_loop_start)
        self.add_loop_end_btn.clicked.connect(self.add_loop_end)
        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self.anti_detect_check.toggled.connect(self.update_anti_detect_settings)
    def update_anti_detect_settings(self, enabled):
        self.random_delay_spin.setEnabled(enabled)
        self.micro_movement_spin.setEnabled(enabled)
    def show_context_menu(self, position):
        row = self.actions_table.rowAt(position.y())
        if row < 0:
            return
        menu = QMenu(self)
        edit_action = menu.addAction("Изменить")
        edit_action.triggered.connect(lambda: self.edit_action())
        delete_action = menu.addAction("Удалить")
        delete_action.triggered.connect(lambda: self.delete_action())
        menu.addSeparator()
        move_up_action = menu.addAction("Переместить вверх")
        move_up_action.triggered.connect(lambda: self.move_action_up())
        move_down_action = menu.addAction("Переместить вниз")
        move_down_action.triggered.connect(lambda: self.move_action_down())
        menu.exec(self.actions_table.mapToGlobal(position))
    def add_action(self):
        dialog = ActionEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            action_type, key, second_key, delay = dialog.get_action_data()
            row = self.actions_table.currentRow()
            if row < 0:
                row = self.actions_table.rowCount()
            self.actions_table.insertRow(row)
            self.actions_table.setItem(row, 0, QTableWidgetItem(action_type))
            self.actions_table.setItem(row, 1, QTableWidgetItem(key))
            self.actions_table.setItem(row, 2, QTableWidgetItem(second_key))
            self.actions_table.setItem(row, 3, QTableWidgetItem(str(delay)))
    def edit_action(self):
        row = self.actions_table.currentRow()
        if row < 0:
            return
        action_type = self.actions_table.item(row, 0).text()
        key = self.actions_table.item(row, 1).text()
        second_key = self.actions_table.item(row, 2).text() if self.actions_table.item(row, 2) else ""
        delay = self.actions_table.item(row, 3).text()
        dialog = ActionEditDialog(action_type, key, second_key, delay, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            action_type, key, second_key, delay = dialog.get_action_data()
            self.actions_table.setItem(row, 0, QTableWidgetItem(action_type))
            self.actions_table.setItem(row, 1, QTableWidgetItem(key))
            self.actions_table.setItem(row, 2, QTableWidgetItem(second_key))
            self.actions_table.setItem(row, 3, QTableWidgetItem(str(delay)))
    def delete_action(self):
        row = self.actions_table.currentRow()
        if row >= 0:
            self.actions_table.removeRow(row)
    def move_action_up(self):
        row = self.actions_table.currentRow()
        if row > 0:
            items = []
            for col in range(self.actions_table.columnCount()):
                item = self.actions_table.takeItem(row, col)
                items.append(item)
            self.actions_table.removeRow(row)
            self.actions_table.insertRow(row - 1)
            for col, item in enumerate(items):
                self.actions_table.setItem(row - 1, col, item)
            self.actions_table.setCurrentCell(row - 1, 0)
    def move_action_down(self):
        row = self.actions_table.currentRow()
        if row >= 0 and row < self.actions_table.rowCount() - 1:
            items = []
            for col in range(self.actions_table.columnCount()):
                item = self.actions_table.takeItem(row, col)
                items.append(item)
            self.actions_table.removeRow(row)
            self.actions_table.insertRow(row + 1)
            for col, item in enumerate(items):
                self.actions_table.setItem(row + 1, col, item)
            self.actions_table.setCurrentCell(row + 1, 0)
    def load_macro_data(self):
        if not self.macro:
            return
        self.name_edit.setText(self.macro.name)
        self.hotkey_edit.setText(self.macro.hotkey)
        self.enabled_check.setChecked(self.macro.enabled)
        self.simplified_display_check.setChecked(self.macro.simplified_display)
        self.voice_command_edit.setText(self.macro.voice_command)
        self.anti_detect_check.setChecked(self.macro.anti_detect_mode)
        self.random_delay_spin.setValue(self.macro.random_delay_percent)
        self.micro_movement_spin.setValue(self.macro.micro_movement_radius)
        self.update_anti_detect_settings(self.macro.anti_detect_mode)
        self.actions_table.setRowCount(0)
        for i, action in enumerate(self.macro.actions):
            self.actions_table.insertRow(i)
            action_type = action.type
            if action.is_loop_start:
                action_type = "loop_start"
            elif action.is_loop_end:
                action_type = "loop_end"
            self.actions_table.setItem(i, 0, QTableWidgetItem(action_type))
            key = ""
            if action.key:
                key = action.key
            elif action.button:
                key = action.button
            self.actions_table.setItem(i, 1, QTableWidgetItem(key))
            self.actions_table.setItem(i, 2, QTableWidgetItem(action.second_key or ""))
            if action_type == "loop_start":
                self.actions_table.setItem(i, 3, QTableWidgetItem(f"Повторений: {action.loop_count}"))
            elif action_type == "loop_end":
                self.actions_table.setItem(i, 3, QTableWidgetItem("Конец цикла"))
            else:
                self.actions_table.setItem(i, 3, QTableWidgetItem(f"{action.delay:.2f}"))
        if self.actions_table.rowCount() > 0:
            self.actions_table.setCurrentCell(0, 0)
    def add_loop_start(self):
        count, ok = QInputDialog.getInt(
            self, "Количество повторений", 
            "Введите количество повторений цикла:", 
            2, 1, 1000, 1
        )
        if ok:
            row = self.actions_table.currentRow()
            if row < 0:
                row = self.actions_table.rowCount()
            self.actions_table.insertRow(row)
            self.actions_table.setItem(row, 0, QTableWidgetItem("loop_start"))
            self.actions_table.setItem(row, 1, QTableWidgetItem(""))
            self.actions_table.setItem(row, 2, QTableWidgetItem(""))
            self.actions_table.setItem(row, 3, QTableWidgetItem(f"Повторений: {count}"))
    def add_loop_end(self):
        row = self.actions_table.currentRow()
        if row < 0:
            row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        self.actions_table.setItem(row, 0, QTableWidgetItem("loop_end"))
        self.actions_table.setItem(row, 1, QTableWidgetItem(""))
        self.actions_table.setItem(row, 2, QTableWidgetItem(""))
        self.actions_table.setItem(row, 3, QTableWidgetItem("Конец цикла"))
    def get_macro_data(self) -> Macro:
        name = self.name_edit.text()
        hotkey = self.hotkey_edit.text()
        enabled = self.enabled_check.isChecked()
        simplified_display = self.simplified_display_check.isChecked()
        anti_detect_mode = self.anti_detect_check.isChecked()
        random_delay_percent = self.random_delay_spin.value()
        micro_movement_radius = self.micro_movement_spin.value()
        voice_command = self.voice_command_edit.text()
        actions = []
        if self.macro:
            actions = self.macro.actions.copy()
        for i in range(self.actions_table.rowCount()):
            action_type = self.actions_table.item(i, 0).text()
            key = self.actions_table.item(i, 1).text() if self.actions_table.item(i, 1) else ""
            second_key = self.actions_table.item(i, 2).text() if self.actions_table.item(i, 2) else ""
            delay_text = self.actions_table.item(i, 3).text() if self.actions_table.item(i, 3) else "0.0"
            try:
                delay = parse_delay_string(delay_text)
            except:
                delay = 0.1
            if i < len(actions):
                action = actions[i]
            else:
                action = MacroAction(type=action_type)
                actions.append(action)
            action.type = action_type
            action.key = key
            action.second_key = second_key
            action.delay = delay
            action.simplified_display = simplified_display
            if action_type == "loop_start":
                action.is_loop_start = True
                action.is_loop_end = False
                loop_text = delay_text
                if "Повторений:" in loop_text:
                    try:
                        count = int(loop_text.split(": ")[1])
                        action.loop_count = count
                    except:
                        action.loop_count = 1
            elif action_type == "loop_end":
                action.is_loop_start = False
                action.is_loop_end = True
            else:
                action.is_loop_start = False
                action.is_loop_end = False
        if self.macro and len(actions) > self.actions_table.rowCount():
            actions = actions[:self.actions_table.rowCount()]
        return Macro(
            name=name,
            actions=actions,
            hotkey=hotkey,
            enabled=enabled,
            created_at=self.macro.created_at if self.macro else datetime.now().isoformat(),
            anti_detect_mode=anti_detect_mode,
            random_delay_percent=random_delay_percent,
            micro_movement_radius=micro_movement_radius,
            simplified_display=simplified_display,
            voice_command=voice_command
        )
class MacroManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Менеджер макросов и автокликер")
        self.setGeometry(100, 100, 800, 600)
        self.macros: List[Macro] = []
        self.macro_recorder = MacroRecorder()
        self.macro_player = MacroPlayer()
        self.hotkey_manager = HotkeyManager(self.macro_player)
        self.auto_clicker = AutoClicker()
        self.setup_ui()
        self.load_macros()
        self.setup_connections()
        self.hotkey_manager.start_listening()
    def find_macro_by_voice_command(self, voice_command: str):
        if not voice_command:
            return None
        voice_command = voice_command.lower().strip()
        for macro in self.macros:
            if macro.enabled and macro.voice_command.lower().strip() == voice_command:
                self.macro_player.play_macro(macro)
                return macro
        return None
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        self.setup_macros_tab()
        self.setup_autoclicker_tab()
    def setup_macros_tab(self):
        macros_widget = QWidget()
        self.tab_widget.addTab(macros_widget, "📁 Макросы")
        layout = QHBoxLayout()
        macros_widget.setLayout(layout)
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_layout.addWidget(QLabel("Список макросов:"))
        self.macros_list = QListWidget()
        left_layout.addWidget(self.macros_list)
        buttons_layout = QHBoxLayout()
        self.add_macro_btn = QPushButton("Добавить")
        self.edit_macro_btn = QPushButton("Редактировать")
        self.delete_macro_btn = QPushButton("Удалить")
        buttons_layout.addWidget(self.add_macro_btn)
        buttons_layout.addWidget(self.edit_macro_btn)
        buttons_layout.addWidget(self.delete_macro_btn)
        left_layout.addLayout(buttons_layout)
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        record_group = QGroupBox("Запись макроса")
        record_layout = QVBoxLayout()
        self.record_status_label = QLabel("Готов к записи")
        self.record_status_label.setStyleSheet("color: green; font-weight: bold;")
        record_layout.addWidget(self.record_status_label)
        record_buttons_layout = QHBoxLayout()
        self.start_record_btn = QPushButton("🔴 Начать запись")
        self.stop_record_btn = QPushButton("⏹️ Остановить запись")
        self.stop_record_btn.setEnabled(False)
        record_buttons_layout.addWidget(self.start_record_btn)
        record_buttons_layout.addWidget(self.stop_record_btn)
        record_layout.addLayout(record_buttons_layout)
        record_layout.addWidget(QLabel("Нажмите ESC для остановки записи"))
        record_group.setLayout(record_layout)
        right_layout.addWidget(record_group)
        playback_group = QGroupBox("Воспроизведение макроса")
        playback_layout = QVBoxLayout()
        playback_buttons_layout = QHBoxLayout()
        self.play_macro_btn = QPushButton("▶️ Воспроизвести выбранный")
        self.stop_macro_btn = QPushButton("⏹️ Остановить воспроизведение")
        self.stop_macro_btn.setEnabled(False)
        playback_buttons_layout.addWidget(self.play_macro_btn)
        playback_buttons_layout.addWidget(self.stop_macro_btn)
        playback_layout.addLayout(playback_buttons_layout)
        playback_group.setLayout(playback_layout)
        right_layout.addWidget(playback_group)
        log_group = QGroupBox("Лог действий")
        log_layout = QVBoxLayout()
        self.actions_log = QTextEdit()
        self.actions_log.setReadOnly(True)
        self.actions_log.setMaximumHeight(200)
        log_layout.addWidget(self.actions_log)
        log_group.setLayout(log_layout)
        right_layout.addWidget(log_group)
        right_layout.addStretch()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter)
    def setup_autoclicker_tab(self):
        autoclicker_widget = QWidget()
        self.tab_widget.addTab(autoclicker_widget, "🖱️ Автокликер")
        layout = QVBoxLayout()
        autoclicker_widget.setLayout(layout)
        settings_group = QGroupBox("Настройки автокликера")
        settings_layout = QFormLayout()
        self.clicks_per_minute_spin = QSpinBox()
        self.clicks_per_minute_spin.setRange(1, 10000)
        self.clicks_per_minute_spin.setValue(60)
        self.clicks_per_minute_spin.setSuffix(" кликов/мин")
        settings_layout.addRow("Скорость:", self.clicks_per_minute_spin)
        self.button_type_combo = QComboBox()
        self.button_type_combo.addItems(["Левая кнопка", "Правая кнопка"])
        settings_layout.addRow("Кнопка мыши:", self.button_type_combo)
        self.anti_detect_check = QCheckBox("Антидетект режим")
        settings_layout.addRow("", self.anti_detect_check)
        self.random_delay_spin = QSpinBox()
        self.random_delay_spin.setRange(0, 100)
        self.random_delay_spin.setValue(20)
        self.random_delay_spin.setSuffix("%")
        settings_layout.addRow("Случайная задержка:", self.random_delay_spin)
        self.micro_movement_spin = QSpinBox()
        self.micro_movement_spin.setRange(0, 20)
        self.micro_movement_spin.setValue(5)
        self.micro_movement_spin.setSuffix(" пикселей")
        settings_layout.addRow("Микродвижения мыши:", self.micro_movement_spin)
        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)
        control_group = QGroupBox("Управление")
        control_layout = QVBoxLayout()
        self.clicker_status_label = QLabel("Остановлен")
        self.clicker_status_label.setStyleSheet("color: red; font-weight: bold;")
        control_layout.addWidget(self.clicker_status_label)
        buttons_layout = QHBoxLayout()
        self.start_clicker_btn = QPushButton("▶️ Запустить")
        self.stop_clicker_btn = QPushButton("⏹️ Остановить")
        self.stop_clicker_btn.setEnabled(False)
        buttons_layout.addWidget(self.start_clicker_btn)
        buttons_layout.addWidget(self.stop_clicker_btn)
        control_layout.addLayout(buttons_layout)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        layout.addStretch()
    def setup_connections(self):
        self.add_macro_btn.clicked.connect(self.add_macro)
        self.edit_macro_btn.clicked.connect(self.edit_macro)
        self.delete_macro_btn.clicked.connect(self.delete_macro)
        self.start_record_btn.clicked.connect(self.start_recording)
        self.stop_record_btn.clicked.connect(self.stop_recording)
        self.macro_recorder.action_recorded.connect(self.on_action_recorded)
        self.macro_recorder.recording_finished.connect(self.on_recording_finished)
        self.start_clicker_btn.clicked.connect(self.start_autoclicker)
        self.stop_clicker_btn.clicked.connect(self.stop_autoclicker)
        self.macros_list.itemDoubleClicked.connect(self.edit_macro)
        self.anti_detect_check.toggled.connect(self.update_anti_detect_settings)
        self.play_macro_btn.clicked.connect(self.play_selected_macro)
        self.stop_macro_btn.clicked.connect(self.stop_macro_playback)
    def update_anti_detect_settings(self, enabled):
        self.random_delay_spin.setEnabled(enabled)
        self.micro_movement_spin.setEnabled(enabled)
    def add_macro(self):
        dialog = MacroEditDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            macro = dialog.get_macro_data()
            if macro.name:
                self.macros.append(macro)
                self.update_macros_list()
                self.save_macros()
                self.update_hotkeys()
    def edit_macro(self):
        current_row = self.macros_list.currentRow()
        if current_row >= 0:
            macro = self.macros[current_row]
            dialog = MacroEditDialog(macro, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                updated_macro = dialog.get_macro_data()
                self.macros[current_row] = updated_macro
                self.update_macros_list()
                self.save_macros()
                self.update_hotkeys()
    def delete_macro(self):
        current_row = self.macros_list.currentRow()
        if current_row >= 0:
            macro = self.macros[current_row]
            reply = QMessageBox.question(
                self, "Подтверждение", 
                f"Удалить макрос '{macro.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.macros.pop(current_row)
                self.update_macros_list()
                self.save_macros()
                self.update_hotkeys()
    def start_recording(self):
        simplified_display = True
        self.macro_recorder.start_recording(simplified_display)
        self.record_status_label.setText("🔴 Запись...")
        self.record_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.start_record_btn.setEnabled(False)
        self.stop_record_btn.setEnabled(True)
        self.actions_log.clear()
    def stop_recording(self):
        self.macro_recorder.stop_recording()
    def on_action_recorded(self, action: MacroAction):
        if action.simplified_display:
            if action.type == 'key_press':
                if action.second_key:
                    action_text = f"Комбинация: {action.second_key}+{action.key} (задержка: {action.delay:.2f}с)"
                else:
                    key_display = action.key
                    if key_display.startswith('Key.'):
                        key_display = key_display[4:]
                    action_text = f"Клавиша: {key_display} (задержка: {action.delay:.2f}с)"
            elif action.type == 'mouse_click':
                button_name = "левая" if "left" in action.button.lower() else "правая"
                action_text = f"Клик {button_name} кнопкой в ({action.x}, {action.y}) (задержка: {action.delay:.2f}с)"
            elif action.type == 'mouse_move':
                action_text = f"Перемещение мыши в ({action.x}, {action.y}) (задержка: {action.delay:.2f}с)"
            else:
                action_text = f"[{action.type}] (задержка: {action.delay:.2f}с)"
        else:
            action_text = f"[{action.type}] "
            if action.key:
                action_text += f"Клавиша: {action.key}"
            elif action.button:
                action_text += f"Кнопка: {action.button}"
            if action.x is not None and action.y is not None:
                action_text += f" в позиции ({action.x}, {action.y})"
            action_text += f" (задержка: {action.delay:.2f}с)"
        self.actions_log.append(action_text)
    def on_recording_finished(self):
        self.record_status_label.setText("Готов к записи")
        self.record_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.start_record_btn.setEnabled(True)
        self.stop_record_btn.setEnabled(False)
        if self.macro_recorder.actions:
            name = f"Макрос {len(self.macros) + 1}"
            macro = Macro(
                name=name,
                actions=self.macro_recorder.actions.copy(),
                created_at=datetime.now().isoformat(),
                anti_detect_mode=self.macro_recorder.anti_detect_mode,
                random_delay_percent=self.macro_recorder.random_delay_percent,
                micro_movement_radius=self.macro_recorder.micro_movement_radius,
                simplified_display=self.macro_recorder.simplified_display
            )
            dialog = MacroEditDialog(macro, parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                updated_macro = dialog.get_macro_data()
                self.macros.append(updated_macro)
                self.update_macros_list()
                self.save_macros()
                self.update_hotkeys()
    def start_autoclicker(self):
        cpm = self.clicks_per_minute_spin.value()
        button_type = 'left' if self.button_type_combo.currentIndex() == 0 else 'right'
        self.auto_clicker.set_anti_detect_mode(self.anti_detect_check.isChecked())
        self.auto_clicker.set_random_delay_percent(self.random_delay_spin.value())
        self.auto_clicker.set_micro_movement_radius(self.micro_movement_spin.value())
        self.auto_clicker.set_clicks_per_minute(cpm)
        self.auto_clicker.set_button_type(button_type)
        self.auto_clicker.start_clicking()
        self.clicker_status_label.setText("🔴 Работает")
        self.clicker_status_label.setStyleSheet("color: green; font-weight: bold;")
        self.start_clicker_btn.setEnabled(False)
        self.stop_clicker_btn.setEnabled(True)
    def stop_autoclicker(self):
        self.auto_clicker.stop_clicking()
        self.clicker_status_label.setText("Остановлен")
        self.clicker_status_label.setStyleSheet("color: red; font-weight: bold;")
        self.start_clicker_btn.setEnabled(True)
        self.stop_clicker_btn.setEnabled(False)
    def update_macros_list(self):
        self.macros_list.clear()
        for macro in self.macros:
            status = "✅" if macro.enabled else "❌"
            hotkey = f" ({macro.hotkey})" if macro.hotkey else ""
            voice_cmd = f" 🎤 \"{macro.voice_command}\"" if macro.voice_command else ""
            text = f"{status} {macro.name}{hotkey}{voice_cmd}"
            self.macros_list.addItem(text)
    def update_hotkeys(self):
        self.hotkey_manager.active_hotkeys.clear()
        for macro in self.macros:
            if macro.hotkey and macro.enabled:
                self.hotkey_manager.register_hotkey(macro.hotkey, macro)
    def save_macros(self):
        try:
            data = [asdict(macro) for macro in self.macros]
            with open('macros.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить макросы: {e}")
    def load_macros(self):
        try:
            if Path('macros.json').exists():
                with open('macros.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.macros = []
                    for item in data:
                        actions = []
                        for action_data in item.get('actions', []):
                            actions.append(MacroAction(**action_data))
                        macro = Macro(
                            name=item['name'],
                            actions=actions,
                            hotkey=item.get('hotkey', ''),
                            enabled=item.get('enabled', True),
                            created_at=item.get('created_at', ''),
                            anti_detect_mode=item.get('anti_detect_mode', False),
                            random_delay_percent=item.get('random_delay_percent', 20),
                            micro_movement_radius=item.get('micro_movement_radius', 5),
                            simplified_display=item.get('simplified_display', True),
                            voice_command=item.get('voice_command', '')
                        )
                        self.macros.append(macro)
                self.update_macros_list()
                self.update_hotkeys()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить макросы: {e}")
    def closeEvent(self, event):
        self.hotkey_manager.stop_listening()
        self.auto_clicker.stop_clicking()
        self.save_macros()
        event.accept()
    def play_selected_macro(self):
        current_row = self.macros_list.currentRow()
        if current_row >= 0:
            macro = self.macros[current_row]
            self.macro_player.play_macro(macro)
            self.play_macro_btn.setEnabled(False)
            self.stop_macro_btn.setEnabled(True)
    def stop_macro_playback(self):
        self.macro_player.stop_playback()
        self.play_macro_btn.setEnabled(True)
        self.stop_macro_btn.setEnabled(False)
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  
    try:
        import pynput
    except ImportError:
        QMessageBox.critical(
            None, "Ошибка", 
            "Необходимо установить библиотеку pynput:\n"
            "pip install pynput"
        )
        return
    window = MacroManagerApp()
    window.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main()