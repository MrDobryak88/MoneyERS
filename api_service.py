
import requests
from xml.etree import ElementTree as ET
import json
from datetime import datetime
from database import insert_historical_rate, get_db_connection
from typing import Dict, Optional

def get_exchange_rates() -> Dict[str, float]:
    """Fetches exchange rates from CBR or loads from file."""
    try:
        url = "http://www.cbr.ru/scripts/XML_daily.asp"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        rates = {}
        for valute in root.findall('.//Valute'):
            char_code = valute.find('CharCode').text
            nominal = float(valute.find('Nominal').text)
            value = float(valute.find('Value').text.replace(',', '.'))
            rates[char_code] = value / nominal
        rates['RUB'] = 1.0
        save_rates_to_file(rates)
        return rates
    except (requests.RequestException, ET.ParseError) as e:
        print(f"Ошибка получения курсов: {e}")
        return load_rates_from_file() or {"USD": 75.0, "EUR": 85.0, "RUB": 1.0}

def save_rates_to_file(rates: Dict[str, float]) -> None:
    """Saves exchange rates to JSON file."""
    try:
        with open('rates.json', 'w') as f:
            json.dump(rates, f, indent=2)
    except IOError as e:
        print(f"Ошибка сохранения курсов: {e}")

def load_rates_from_file() -> Optional[Dict[str, float]]:
    """Loads exchange rates from JSON file."""
    try:
        with open('rates.json', 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Ошибка загрузки курсов: {e}")
        return None

def update_historical_rates() -> None:
    """Updates historical exchange rates if not already updated today."""
    today = datetime.today().strftime('%Y-%m-%d')
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT MAX(date) FROM historical_rates WHERE date = ?", (today,))
        if c.fetchone()[0]:
            return
        rates = get_exchange_rates()
        for char_code, rate in rates.items():
            insert_historical_rate(today, char_code, rate)
