import sys
import os
import json
import requests
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QComboBox, 
                           QLineEdit, QMessageBox, QGridLayout, QDialog)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
WEATHER_API_KEY = "b08681bea8dc12a0892e01f22b6de693"
SETTINGS_FILE = "weather_settings.json"
WEATHER_EMOJI = {
    "Clear": "☀️",
    "Clouds": "☁️",
    "Rain": "🌧️",
    "Drizzle": "🌦️",
    "Thunderstorm": "⛈️",
    "Snow": "❄️",
    "Mist": "🌫️",
    "Fog": "🌫️",
    "Haze": "🌫️",
    "Smoke": "🌫️",
    "Dust": "🌫️",
    "Sand": "🌫️",
    "Ash": "🌫️",
    "Squall": "💨",
    "Tornado": "🌪️"
}
class CitySelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Выбор города")
        self.setMinimumWidth(400)
        self.setModal(True)
        self.selected_city = ""
        self.selected_district = ""
        self.districts = []
        self.init_ui()
    def init_ui(self):
        layout = QVBoxLayout(self)
        city_layout = QHBoxLayout()
        city_label = QLabel("Город:")
        city_label.setFont(QFont("Arial", 12))
        self.city_input = QLineEdit()
        self.city_input.setPlaceholderText("Например: Москва")
        self.search_btn = QPushButton("Поиск")
        self.search_btn.clicked.connect(self.search_city)
        city_layout.addWidget(city_label)
        city_layout.addWidget(self.city_input)
        city_layout.addWidget(self.search_btn)
        layout.addLayout(city_layout)
        district_layout = QHBoxLayout()
        district_label = QLabel("Район:")
        district_label.setFont(QFont("Arial", 12))
        self.district_combo = QComboBox()
        self.district_combo.setEnabled(False)
        district_layout.addWidget(district_label)
        district_layout.addWidget(self.district_combo)
        layout.addLayout(district_layout)
        buttons_layout = QHBoxLayout()
        self.ok_btn = QPushButton("OK")
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.ok_btn)
        buttons_layout.addWidget(cancel_btn)
        layout.addLayout(buttons_layout)
    def search_city(self):
        city_name = self.city_input.text().strip()
        if not city_name:
            QMessageBox.warning(self, "Предупреждение", "Введите название города")
            return
        try:
            geocoding_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city_name}&limit=5&appid={WEATHER_API_KEY}"
            response = requests.get(geocoding_url)
            response.raise_for_status()
            locations = response.json()
            if not locations:
                QMessageBox.warning(self, "Город не найден", f"Город '{city_name}' не найден")
                return
            location = locations[0]
            self.selected_city = location.get("name", city_name)
            lat = location.get("lat")
            lon = location.get("lon")
            nearby_url = f"http://api.openweathermap.org/geo/1.0/reverse?lat={lat}&lon={lon}&limit=10&appid={WEATHER_API_KEY}"
            nearby_response = requests.get(nearby_url)
            nearby_response.raise_for_status()
            nearby_locations = nearby_response.json()
            self.districts = []
            self.district_combo.clear()
            main_district = {
                "name": self.selected_city,
                "lat": lat,
                "lon": lon
            }
            self.districts.append(main_district)
            self.district_combo.addItem(f"{self.selected_city} (центр)")
            for loc in nearby_locations:
                if loc.get("name") != self.selected_city:
                    district = {
                        "name": loc.get("name"),
                        "lat": loc.get("lat"),
                        "lon": loc.get("lon")
                    }
                    self.districts.append(district)
                    self.district_combo.addItem(loc.get("name"))
            self.district_combo.setEnabled(True)
            self.ok_btn.setEnabled(True)
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при поиске города: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Неизвестная ошибка: {str(e)}")
    def get_selected_location(self):
        district_index = self.district_combo.currentIndex()
        if district_index >= 0 and district_index < len(self.districts):
            selected_district = self.districts[district_index]
            return {
                "city": self.selected_city,
                "district": selected_district.get("name"),
                "lat": selected_district.get("lat"),
                "lon": selected_district.get("lon")
            }
        return None
class WeatherApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Прогноз погоды")
        self.setMinimumSize(500, 400)
        self.location = None
        self.weather_data = None
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_weather)
        self.update_timer.setInterval(60 * 1000)  
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.setInterval(1000)  
        self.init_ui()
        self.load_settings()
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.location_label = QLabel("Местоположение не выбрано")
        self.location_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.location_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.location_label)
        self.time_label = QLabel("--:--:--")
        self.time_label.setFont(QFont("Arial", 14))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.time_label)
        weather_widget = QWidget()
        weather_layout = QGridLayout(weather_widget)
        temp_label = QLabel("Температура:")
        temp_label.setFont(QFont("Arial", 12))
        self.temp_value = QLabel("--°C")
        self.temp_value.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        weather_layout.addWidget(temp_label, 0, 0)
        weather_layout.addWidget(self.temp_value, 0, 1)
        feels_like_label = QLabel("Ощущается как:")
        feels_like_label.setFont(QFont("Arial", 12))
        self.feels_like_value = QLabel("--°C")
        self.feels_like_value.setFont(QFont("Arial", 12))
        weather_layout.addWidget(feels_like_label, 1, 0)
        weather_layout.addWidget(self.feels_like_value, 1, 1)
        conditions_label = QLabel("Погодные условия:")
        conditions_label.setFont(QFont("Arial", 12))
        self.conditions_value = QLabel("--")
        self.conditions_value.setFont(QFont("Arial", 12))
        weather_layout.addWidget(conditions_label, 2, 0)
        weather_layout.addWidget(self.conditions_value, 2, 1)
        humidity_label = QLabel("Влажность:")
        humidity_label.setFont(QFont("Arial", 12))
        self.humidity_value = QLabel("--%")
        self.humidity_value.setFont(QFont("Arial", 12))
        weather_layout.addWidget(humidity_label, 3, 0)
        weather_layout.addWidget(self.humidity_value, 3, 1)
        pressure_label = QLabel("Давление:")
        pressure_label.setFont(QFont("Arial", 12))
        self.pressure_value = QLabel("-- гПа")
        self.pressure_value.setFont(QFont("Arial", 12))
        weather_layout.addWidget(pressure_label, 4, 0)
        weather_layout.addWidget(self.pressure_value, 4, 1)
        wind_label = QLabel("Скорость ветра:")
        wind_label.setFont(QFont("Arial", 12))
        self.wind_value = QLabel("-- м/с")
        self.wind_value.setFont(QFont("Arial", 12))
        weather_layout.addWidget(wind_label, 5, 0)
        weather_layout.addWidget(self.wind_value, 5, 1)
        update_time_label = QLabel("Последнее обновление:")
        update_time_label.setFont(QFont("Arial", 12))
        self.update_time_value = QLabel("--")
        self.update_time_value.setFont(QFont("Arial", 12))
        weather_layout.addWidget(update_time_label, 6, 0)
        weather_layout.addWidget(self.update_time_value, 6, 1)
        main_layout.addWidget(weather_widget)
        buttons_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        refresh_btn.setMinimumHeight(40)
        refresh_btn.clicked.connect(self.update_weather)
        buttons_layout.addWidget(refresh_btn)
        change_location_btn = QPushButton("Изменить местоположение")
        change_location_btn.setMinimumHeight(40)
        change_location_btn.clicked.connect(self.change_location)
        buttons_layout.addWidget(change_location_btn)
        main_layout.addLayout(buttons_layout)
    def load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as file:
                    settings = json.load(file)
                    self.location = settings.get('location')
                    if self.location:
                        self.update_location_display()
                        self.update_weather()
                        self.time_timer.start()
                    else:
                        self.change_location()
            else:
                self.change_location()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить настройки: {str(e)}")
            self.change_location()
    def save_settings(self):
        try:
            settings = {
                'location': self.location,
                'last_update': datetime.now().isoformat()
            }
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as file:
                json.dump(settings, file, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось сохранить настройки: {str(e)}")
    def change_location(self):
        dialog = CitySelectionDialog(self)
        if dialog.exec():
            self.location = dialog.get_selected_location()
            if self.location:
                self.update_location_display()
                self.save_settings()
                self.update_weather()
                self.time_timer.start()
    def update_location_display(self):
        if self.location:
            city = self.location.get('city', '')
            district = self.location.get('district', '')
            if district and district != city:
                self.location_label.setText(f"{city}, {district}")
            else:
                self.location_label.setText(city)
    def update_time(self):
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        self.time_label.setText(time_str)
    def update_weather(self):
        if not self.location:
            return
        try:
            lat = self.location.get('lat')
            lon = self.location.get('lon')
            url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&lang=ru&appid={WEATHER_API_KEY}"
            response = requests.get(url)
            response.raise_for_status()
            self.weather_data = response.json()
            self.display_weather()
            if not self.update_timer.isActive():
                self.update_timer.start()
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при получении данных о погоде: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Неизвестная ошибка: {str(e)}")
    def display_weather(self):
        if not self.weather_data:
            return
        temp = self.weather_data.get('main', {}).get('temp')
        if temp is not None:
            self.temp_value.setText(f"{temp:.1f}°C")
        feels_like = self.weather_data.get('main', {}).get('feels_like')
        if feels_like is not None:
            self.feels_like_value.setText(f"{feels_like:.1f}°C")
        weather = self.weather_data.get('weather', [{}])[0]
        weather_main = weather.get('main', '')
        weather_description = weather.get('description', '')
        emoji = WEATHER_EMOJI.get(weather_main, '')
        if emoji and weather_description:
            self.conditions_value.setText(f"{emoji} {weather_description.capitalize()}")
        elif weather_description:
            self.conditions_value.setText(weather_description.capitalize())
        humidity = self.weather_data.get('main', {}).get('humidity')
        if humidity is not None:
            self.humidity_value.setText(f"{humidity}%")
        pressure = self.weather_data.get('main', {}).get('pressure')
        if pressure is not None:
            pressure_mmhg = pressure * 0.75006  
            self.pressure_value.setText(f"{pressure_mmhg:.0f} мм рт.ст.")
        wind_speed = self.weather_data.get('wind', {}).get('speed')
        if wind_speed is not None:
            self.wind_value.setText(f"{wind_speed} м/с")
        now = datetime.now()
        self.update_time_value.setText(now.strftime("%d.%m.%Y %H:%M:%S"))
        self.save_weather_data()
    def save_weather_data(self):
        if not self.weather_data or not self.location:
            return
        try:
            city = self.location.get('city', '')
            district = self.location.get('district', '')
            save_data = {
                'location': {
                    'city': city,
                    'district': district,
                    'lat': self.location.get('lat'),
                    'lon': self.location.get('lon')
                },
                'weather': self.weather_data,
                'last_update': datetime.now().isoformat()
            }
            filename = f"weather_{city.lower()}_{district.lower()}.json".replace(' ', '_')
            with open(filename, 'w', encoding='utf-8') as file:
                json.dump(save_data, file, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Ошибка при сохранении данных о погоде: {str(e)}")
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  
    window = WeatherApp()
    window.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main() 