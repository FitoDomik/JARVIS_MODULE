import sys
import json
import requests
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QComboBox, 
                           QLineEdit, QMessageBox, QGridLayout, QTabWidget,
                           QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
EXCHANGE_API_KEY = "YOUR_API_KEY_HERE"  
CRYPTO_API_URL = "https://api.coingecko.com/api/v3"
SETTINGS_FILE = "currency_settings.json"
TOP_CURRENCIES = [
    {"code": "USD", "name": "Доллар США", "symbol": "$"},
    {"code": "EUR", "name": "Евро", "symbol": "€"},
    {"code": "GBP", "name": "Фунт стерлингов", "symbol": "£"},
    {"code": "JPY", "name": "Японская иена", "symbol": "¥"},
    {"code": "CNY", "name": "Китайский юань", "symbol": "¥"},
    {"code": "RUB", "name": "Российский рубль", "symbol": "₽"},
    {"code": "CHF", "name": "Швейцарский франк", "symbol": "CHF"},
    {"code": "CAD", "name": "Канадский доллар", "symbol": "C$"},
    {"code": "AUD", "name": "Австралийский доллар", "symbol": "A$"},
    {"code": "NZD", "name": "Новозеландский доллар", "symbol": "NZ$"}
]
TOP_CRYPTOS = [
    {"id": "bitcoin", "name": "Bitcoin", "symbol": "BTC"},
    {"id": "ethereum", "name": "Ethereum", "symbol": "ETH"},
    {"id": "binancecoin", "name": "BNB", "symbol": "BNB"},
    {"id": "solana", "name": "Solana", "symbol": "SOL"},
    {"id": "cardano", "name": "Cardano", "symbol": "ADA"},
    {"id": "ripple", "name": "XRP", "symbol": "XRP"},
    {"id": "polkadot", "name": "Polkadot", "symbol": "DOT"},
    {"id": "dogecoin", "name": "Dogecoin", "symbol": "DOGE"},
    {"id": "avalanche-2", "name": "Avalanche", "symbol": "AVAX"},
    {"id": "chainlink", "name": "Chainlink", "symbol": "LINK"}
]
CURRENCY_SEARCH_DICT = {
    "рубль": "RUB", "руб": "RUB", "рубль": "RUB", "рубаль": "RUB", "рубли": "RUB",
    "доллар": "USD", "доллары": "USD", "долларсша": "USD", "долларсша": "USD",
    "евро": "EUR", "евро": "EUR", "евро": "EUR",
    "фунт": "GBP", "фунтстерлингов": "GBP", "фунтстерлингов": "GBP",
    "иена": "JPY", "иена": "JPY", "иена": "JPY", "иена": "JPY",
    "юань": "CNY", "юань": "CNY", "юань": "CNY", "юань": "CNY",
    "франк": "CHF", "франк": "CHF", "франк": "CHF", "франк": "CHF",
    "канадский": "CAD", "канадскийдоллар": "CAD", "канадскийдоллар": "CAD",
    "австралийский": "AUD", "австралийскийдоллар": "AUD", "австралийскийдоллар": "AUD",
    "новозеландский": "NZD", "новозеландскийдоллар": "NZD", "новозеландскийдоллар": "NZD"
}
class CurrencyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Курсы валют и криптовалют")
        self.setMinimumSize(800, 600)
        self.currency_rates = {}
        self.crypto_rates = {}
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_all_rates)
        self.update_timer.setInterval(5 * 60 * 1000)  
        self.init_ui()
        self.load_currency_rates()
        self.load_crypto_rates()
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        tabs = QTabWidget()
        main_layout.addWidget(tabs)
        currency_tab = self.create_currency_tab()
        tabs.addTab(currency_tab, "Курсы валют")
        crypto_tab = self.create_crypto_tab()
        tabs.addTab(crypto_tab, "Курсы криптовалют")
        converter_tab = self.create_converter_tab()
        tabs.addTab(converter_tab, "Переводчик валют")
        buttons_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить все курсы")
        refresh_btn.setMinimumHeight(40)
        refresh_btn.clicked.connect(self.update_all_rates)
        buttons_layout.addWidget(refresh_btn)
        self.auto_update_btn = QPushButton("Включить автообновление")
        self.auto_update_btn.setMinimumHeight(40)
        self.auto_update_btn.clicked.connect(self.toggle_auto_update)
        buttons_layout.addWidget(self.auto_update_btn)
        main_layout.addLayout(buttons_layout)
    def create_currency_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        title_label = QLabel("Курсы валют к рублю")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск валюты:")
        search_label.setFont(QFont("Arial", 12))
        self.currency_search = QLineEdit()
        self.currency_search.setPlaceholderText("Например: доллар, евро, рубль...")
        self.currency_search.textChanged.connect(self.search_currency)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.currency_search)
        layout.addLayout(search_layout)
        self.currency_table = QTableWidget()
        self.currency_table.setColumnCount(4)
        self.currency_table.setHorizontalHeaderLabels(["Валюта", "Код", "Курс к рублю", "Изменение"])
        header = self.currency_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.currency_table)
        return tab
    def create_crypto_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        title_label = QLabel("Курсы криптовалют")
        title_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        search_layout = QHBoxLayout()
        search_label = QLabel("Поиск криптовалюты:")
        search_label.setFont(QFont("Arial", 12))
        self.crypto_search = QLineEdit()
        self.crypto_search.setPlaceholderText("Например: bitcoin, ethereum...")
        self.crypto_search.textChanged.connect(self.search_crypto)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.crypto_search)
        layout.addLayout(search_layout)
        self.crypto_table = QTableWidget()
        self.crypto_table.setColumnCount(5)
        self.crypto_table.setHorizontalHeaderLabels(["Название", "Символ", "Цена (USD)", "Изменение 24ч", "Рыночная капитализация"])
        header = self.crypto_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.crypto_table)
        return tab
    def create_converter_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(18)
        layout.setContentsMargins(60, 40, 60, 40)
        title_label = QLabel("Переводчик валют")
        title_label.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        self.from_currency = QComboBox()
        self.from_currency.setFixedHeight(48)
        self.from_currency.setFont(QFont("Arial", 16))
        self.from_currency.addItems([f"{curr['code']} - {curr['name']}" for curr in TOP_CURRENCIES])
        self.from_currency.currentIndexChanged.connect(self.convert_currency)
        layout.addWidget(self.from_currency)
        swap_btn = QPushButton("⇄")
        swap_btn.setFixedHeight(44)
        swap_btn.setFont(QFont("Arial", 22, QFont.Weight.Bold))
        swap_btn.clicked.connect(self.swap_currencies)
        layout.addWidget(swap_btn)
        self.to_currency = QComboBox()
        self.to_currency.setFixedHeight(48)
        self.to_currency.setFont(QFont("Arial", 16))
        self.to_currency.addItems([f"{curr['code']} - {curr['name']}" for curr in TOP_CURRENCIES])
        self.to_currency.setCurrentText("RUB - Российский рубль")
        self.to_currency.currentIndexChanged.connect(self.convert_currency)
        layout.addWidget(self.to_currency)
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Введите сумму")
        self.amount_input.setFixedHeight(48)
        self.amount_input.setFont(QFont("Arial", 16))
        self.amount_input.textChanged.connect(self.convert_currency)
        layout.addWidget(self.amount_input)
        convert_btn = QPushButton("Конвертировать")
        convert_btn.setFixedHeight(48)
        convert_btn.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        convert_btn.clicked.connect(self.convert_currency)
        layout.addWidget(convert_btn)
        self.result_label = QLabel("--")
        self.result_label.setFont(QFont("Arial", 40, QFont.Weight.Bold))
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.result_label)
        return tab
    def search_currency(self, text):
        if not text:
            self.update_currency_table()
            return
        search_text = text.lower().replace(" ", "")
        found_currency = None
        for key, value in CURRENCY_SEARCH_DICT.items():
            if search_text in key:
                found_currency = value
                break
        if not found_currency:
            for currency in TOP_CURRENCIES:
                if search_text in currency['code'].lower() or search_text in currency['name'].lower():
                    found_currency = currency['code']
                    break
        if found_currency:
            self.update_currency_table(found_currency)
        else:
            self.update_currency_table()
    def search_crypto(self, text):
        if not text:
            self.update_crypto_table()
            return
        search_text = text.lower()
        found_crypto = None
        for crypto in TOP_CRYPTOS:
            if (search_text in crypto['name'].lower() or 
                search_text in crypto['symbol'].lower() or
                search_text in crypto['id'].lower()):
                found_crypto = crypto['id']
                break
        if found_crypto:
            self.update_crypto_table(found_crypto)
        else:
            self.update_crypto_table()
    def load_currency_rates(self):
        try:
            url = "https://api.exchangerate-api.com/v4/latest/RUB"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            self.currency_rates = data.get('rates', {})
            self.update_currency_table()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить курсы валют: {str(e)}")
    def load_crypto_rates(self):
        try:
            crypto_ids = [crypto['id'] for crypto in TOP_CRYPTOS]
            ids_string = ','.join(crypto_ids)
            url = f"{CRYPTO_API_URL}/simple/price?ids={ids_string}&vs_currencies=usd&include_24hr_change=true&include_market_cap=true"
            response = requests.get(url)
            response.raise_for_status()
            self.crypto_rates = response.json()
            self.update_crypto_table()
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить курсы криптовалют: {str(e)}")
    def update_currency_table(self, highlight_currency=None):
        self.currency_table.setRowCount(0)
        for i, currency in enumerate(TOP_CURRENCIES):
            if currency['code'] in self.currency_rates:
                rate = self.currency_rates[currency['code']]
                self.currency_table.insertRow(i)
                name_item = QTableWidgetItem(f"{currency['symbol']} {currency['name']}")
                self.currency_table.setItem(i, 0, name_item)
                code_item = QTableWidgetItem(currency['code'])
                self.currency_table.setItem(i, 1, code_item)
                rate_item = QTableWidgetItem(f"{rate:.4f}")
                self.currency_table.setItem(i, 2, rate_item)
                change_item = QTableWidgetItem("--")
                self.currency_table.setItem(i, 3, change_item)
                if highlight_currency and currency['code'] == highlight_currency:
                    for j in range(4):
                        item = self.currency_table.item(i, j)
                        if item:
                            item.setBackground(Qt.GlobalColor.yellow)
    def update_crypto_table(self, highlight_crypto=None):
        self.crypto_table.setRowCount(0)
        for i, crypto in enumerate(TOP_CRYPTOS):
            if crypto['id'] in self.crypto_rates:
                crypto_data = self.crypto_rates[crypto['id']]
                self.crypto_table.insertRow(i)
                name_item = QTableWidgetItem(crypto['name'])
                self.crypto_table.setItem(i, 0, name_item)
                symbol_item = QTableWidgetItem(crypto['symbol'])
                self.crypto_table.setItem(i, 1, symbol_item)
                price = crypto_data.get('usd', 0)
                price_item = QTableWidgetItem(f"${price:.2f}")
                self.crypto_table.setItem(i, 2, price_item)
                change_24h = crypto_data.get('usd_24h_change', 0)
                change_item = QTableWidgetItem(f"{change_24h:.2f}%")
                if change_24h > 0:
                    change_item.setForeground(Qt.GlobalColor.green)
                elif change_24h < 0:
                    change_item.setForeground(Qt.GlobalColor.red)
                self.crypto_table.setItem(i, 3, change_item)
                market_cap = crypto_data.get('usd_market_cap', 0)
                if market_cap > 1e9:
                    market_cap_str = f"${market_cap/1e9:.2f}B"
                elif market_cap > 1e6:
                    market_cap_str = f"${market_cap/1e6:.2f}M"
                else:
                    market_cap_str = f"${market_cap:.0f}"
                market_cap_item = QTableWidgetItem(market_cap_str)
                self.crypto_table.setItem(i, 4, market_cap_item)
                if highlight_crypto and crypto['id'] == highlight_crypto:
                    for j in range(5):
                        item = self.crypto_table.item(i, j)
                        if item:
                            item.setBackground(Qt.GlobalColor.yellow)
    def swap_currencies(self):
        from_index = self.from_currency.currentIndex()
        to_index = self.to_currency.currentIndex()
        self.from_currency.setCurrentIndex(to_index)
        self.to_currency.setCurrentIndex(from_index)
        self.convert_currency()
    def convert_currency(self):
        try:
            from_currency = self.from_currency.currentText().split(" - ")[0]
            to_currency = self.to_currency.currentText().split(" - ")[0]
            amount_text = self.amount_input.text().strip()
            if not amount_text:
                self.result_label.setText("--")
                return
            amount = float(amount_text)
            url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            rates = data.get('rates', {})
            if to_currency in rates:
                converted_amount = amount * rates[to_currency]
                self.result_label.setText(f"{converted_amount:.2f} {to_currency}")
            else:
                self.result_label.setText("Ошибка конвертации")
        except ValueError:
            self.result_label.setText("Неверная сумма")
        except Exception as e:
            self.result_label.setText("Ошибка конвертации")
    def update_all_rates(self):
        self.load_currency_rates()
        self.load_crypto_rates()
    def toggle_auto_update(self):
        if self.update_timer.isActive():
            self.update_timer.stop()
            self.auto_update_btn.setText("Включить автообновление")
        else:
            self.update_timer.start()
            self.auto_update_btn.setText("Выключить автообновление")
def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = CurrencyApp()
    window.show()
    sys.exit(app.exec())
if __name__ == "__main__":
    main() 