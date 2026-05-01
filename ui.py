import customtkinter as ctk
import csv
from datetime import datetime, timedelta
from PIL import Image
from database import update_user_password
import io
import matplotlib.pyplot as plt
from database import check_login, add_user, get_user_stats, get_user_transactions, get_user_creation_date
from api_service import get_exchange_rates
from typing import Dict, Optional, Callable, List, Tuple

ctk.set_appearance_mode("Light")

class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Обмен валют - Вход")
        self.geometry("400x300")
        self.resizable(False, False)
        self._setup_ui()

    def wm_protocol(self, name: str, func: Callable) -> None:
        """Custom wm_protocol to fix TypeError in Python 3.13."""
        if name == "WM_DELETE_WINDOW" and func:
            self._root().wm_protocol(name, self.destroy)
        else:
            super().wm_protocol(name, func)

    def _setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        frame = ctk.CTkFrame(self)
        frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        frame.grid_rowconfigure((0, 1, 2, 3, 4), weight=1)
        frame.grid_columnconfigure(0, weight=1)

        self.username_entry = ctk.CTkEntry(frame, placeholder_text="Имя пользователя")
        self.username_entry.grid(row=0, column=0, sticky="ew", pady=10)

        self.password_entry = ctk.CTkEntry(frame, placeholder_text="Пароль", show="*")
        self.password_entry.grid(row=1, column=0, sticky="ew", pady=10)

        ctk.CTkButton(frame, text="Войти", command=self._login).grid(row=2, column=0, sticky="ew", pady=5)
        ctk.CTkButton(frame, text="Зарегистрироваться", command=self._register_user).grid(row=3, column=0, sticky="ew", pady=5)

        self.message_label = ctk.CTkLabel(frame, text="")
        self.message_label.grid(row=4, column=0, pady=5)

    def _login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not (username and password):
            self.message_label.configure(text="Заполните все поля")
            return
        user_id = check_login(username, password)
        if user_id:
            self.destroy()
            MainWindow(username, user_id).mainloop()
        else:
            self.message_label.configure(text="Неверные данные")

    def _register_user(self):  # Renamed from _register
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not (username and password):
            self.message_label.configure(text="Заполните все поля")
            return
        if add_user(username, password):
            self.message_label.configure(text="Регистрация успешна")
        else:
            self.message_label.configure(text="Имя занято")

class MainWindow(ctk.CTk):
    def __init__(self, username: str, user_id: int):
        super().__init__()
        self.title(f"Обмен валют - {username}")
        self.geometry("800x600")
        self.username = username
        self.user_id = user_id
        self.rates = get_exchange_rates()
        self._setup_ui()

    def _setup_ui(self):
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabview.add("Конвертация")
        self.tabview.add("История")
        self.tabview.add("Аналитика")
        self.tabview.add("Настройки")
        self.tabview.add("Профиль")
        self._setup_convert_tab()
        self._setup_history_tab()
        self._setup_analytics_tab()
        self._setup_settings_tab()
        self._setup_profile_tab()

    def _setup_convert_tab(self):
        frame = self.tabview.tab("Конвертация")
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(frame, text="Из:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.from_var = ctk.StringVar(value="USD")
        self.from_combo = ctk.CTkComboBox(frame, variable=self.from_var, values=list(self.rates.keys()))
        self.from_combo.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(frame, text="В:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.to_var = ctk.StringVar(value="EUR")
        self.to_combo = ctk.CTkComboBox(frame, variable=self.to_var, values=list(self.rates.keys()))
        self.to_combo.grid(row=1, column=1, sticky="w")

        ctk.CTkLabel(frame, text="Сумма:").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.amount_entry = ctk.CTkEntry(frame)
        self.amount_entry.grid(row=2, column=1, sticky="w")

        ctk.CTkButton(frame, text="Конвертировать", command=self._convert).grid(row=3, column=0, columnspan=2, pady=10)
        self.result_label = ctk.CTkLabel(frame, text="")
        self.result_label.grid(row=4, column=0, columnspan=2, pady=10)
        self.alert_label = ctk.CTkLabel(frame, text="")
        self.alert_label.grid(row=5, column=0, columnspan=2, pady=10)

    def _convert(self):
        try:
            amount = float(self.amount_entry.get())
            if amount <= 0:
                raise ValueError("Сумма должна быть положительной")
            from_curr, to_curr = self.from_var.get(), self.to_var.get()
            rate = self.rates[from_curr] / self.rates[to_curr]
            result = amount * rate
            self.result_label.configure(text=f"{amount:.2f} {from_curr} = {result:.2f} {to_curr}")
            self._log_transaction(from_curr, to_curr, amount, rate)
            self._check_alert(rate if from_curr == "USD" and to_curr == "EUR" else None)
        except ValueError as e:
            self.result_label.configure(text=str(e))

    def _log_transaction(self, from_curr: str, to_curr: str, amount: float, rate: float):
        from database import get_db_connection
        with get_db_connection() as conn:
            c = conn.cursor()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("INSERT INTO transactions (user_id, from_currency, to_currency, amount, rate, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                     (self.user_id, from_curr, to_curr, amount, rate, timestamp))
            conn.commit()

    def _setup_history_tab(self):
        frame = self.tabview.tab("История")
        frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Панель для фильтров
        filter_frame = ctk.CTkFrame(frame)
        filter_frame.grid(row=0, column=0, columnspan=4, pady=10, sticky="ew")
        filter_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Фильтр по дате
        ctk.CTkLabel(filter_frame, text="Дата (ГГГГ-ММ-ДД):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.date_filter_entry = ctk.CTkEntry(filter_frame)
        self.date_filter_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Фильтр по валюте
        ctk.CTkLabel(filter_frame, text="Валюта:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.currency_filter_var = ctk.StringVar(value="")
        self.currency_filter_combo = ctk.CTkComboBox(
            filter_frame,
            variable=self.currency_filter_var,
            values=["", "USD", "EUR", "RUB", "AED"]
        )
        self.currency_filter_combo.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # Кнопка применения фильтров
        ctk.CTkButton(filter_frame, text="Применить фильтры", command=self._apply_filters).grid(
            row=0, column=4, padx=5, pady=5
        )

        # Таблица для отображения данных
        self.history_table_frame = ctk.CTkScrollableFrame(frame)
        self.history_table_frame.grid(row=1, column=0, columnspan=4, pady=10, sticky="nsew")

        # Пагинация
        pagination_frame = ctk.CTkFrame(frame)
        pagination_frame.grid(row=2, column=0, columnspan=4, pady=10, sticky="ew")
        pagination_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.page_var = ctk.IntVar(value=1)
        self.total_pages = 1

        ctk.CTkButton(pagination_frame, text="<<", command=lambda: self._change_page(-1)).grid(
            row=0, column=0, padx=5, pady=5
        )
        self.page_label = ctk.CTkLabel(pagination_frame, text="Страница 1 из 1")
        self.page_label.grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkButton(pagination_frame, text=">>", command=lambda: self._change_page(1)).grid(
            row=0, column=2, padx=5, pady=5
        )

        # Загрузка данных
        self.transactions = []
        self.filtered_transactions = []
        self._load_transactions()

    def _load_transactions(self):
        """Загружает все транзакции пользователя."""
        from database import get_db_connection
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute(
                "SELECT from_currency, to_currency, amount, rate, timestamp FROM transactions WHERE user_id = ? ORDER BY timestamp DESC",
                (self.user_id,)
            )
            self.transactions = c.fetchall()
            self.filtered_transactions = self.transactions
            self._update_table()

    def _apply_filters(self):
        """Применяет фильтры к данным."""
        date_filter = self.date_filter_entry.get().strip()
        currency_filter = self.currency_filter_var.get().upper()

        self.filtered_transactions = [
            t for t in self.transactions
            if (not date_filter or t[4].startswith(date_filter)) and
               (not currency_filter or currency_filter in (t[0], t[1]))
        ]
        self._update_table()

    def _update_table(self):
        """Обновляет таблицу с учетом фильтров и пагинации."""
        for widget in self.history_table_frame.winfo_children():
            widget.destroy()

        # Пагинация
        page_size = 20
        self.total_pages = (len(self.filtered_transactions) + page_size - 1) // page_size
        current_page = max(1, min(self.page_var.get(), self.total_pages))
        self.page_var.set(current_page)
        self.page_label.configure(text=f"Страница {current_page} из {self.total_pages}")

        start_index = (current_page - 1) * page_size
        end_index = start_index + page_size
        displayed_transactions = self.filtered_transactions[start_index:end_index]

        # Отображение данных
        for i, (from_curr, to_curr, amount, rate, timestamp) in enumerate(displayed_transactions):
            bg_color = "#f0f0f0" if i % 2 == 0 else "#ffffff"
            row_frame = ctk.CTkFrame(self.history_table_frame, fg_color=bg_color)
            row_frame.grid(row=i, column=0, sticky="ew", pady=2)

            ctk.CTkLabel(row_frame, text=timestamp, anchor="w").grid(row=0, column=0, padx=10, sticky="w")
            ctk.CTkLabel(row_frame, text=f"{amount:.2f} {from_curr} -> {amount * rate:.2f} {to_curr}", anchor="w").grid(
                row=0, column=1, padx=10, sticky="w"
            )

    def _change_page(self, direction: int):
        """Переключает страницу."""
        current_page = self.page_var.get()
        new_page = current_page + direction
        if 1 <= new_page <= self.total_pages:
            self.page_var.set(new_page)
            self._update_table()

    def _setup_analytics_tab(self):
        frame = self.tabview.tab("Аналитика")
        frame.grid_columnconfigure((0, 1), weight=1)

        # Выбор пары валют
        ctk.CTkLabel(frame, text="Пара валют:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.pair_var = ctk.StringVar(value="USD/EUR")
        self.pair_combo = ctk.CTkComboBox(
            frame,
            variable=self.pair_var,
            values=["USD/EUR", "USD/RUB", "EUR/RUB", "AED/RUB"]
        )
        self.pair_combo.grid(row=0, column=1, sticky="w")

        # Выбор периода (дней назад)
        ctk.CTkLabel(frame, text="Дней назад:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.days_entry = ctk.CTkEntry(frame)
        self.days_entry.grid(row=1, column=1, sticky="w")

        # Кнопка для построения графика
        ctk.CTkButton(frame, text="Показать график", command=self._plot_conversion_history).grid(
            row=2, column=0, columnspan=2, pady=10
        )

        # Экспорт данных
        export_frame = ctk.CTkFrame(frame)
        export_frame.grid(row=3, column=0, columnspan=2, pady=10)
        ctk.CTkButton(export_frame, text="Экспорт в CSV", command=self._export_to_csv).pack(side="left", padx=5)
        ctk.CTkButton(export_frame, text="Экспорт в PNG", command=self._export_graph_to_png).pack(side="left", padx=5)

        # Отображение графика
        self.graph_label = ctk.CTkLabel(frame, text="")
        self.graph_label.grid(row=4, column=0, columnspan=2, pady=10)

        # Статистика
        self.stats_label = ctk.CTkLabel(frame, text="", justify="left")
        self.stats_label.grid(row=5, column=0, columnspan=2, pady=10)

    def _plot_conversion_history(self):
        pair = self.pair_var.get().split('/')
        try:
            days = int(self.days_entry.get())
            if days <= 0:
                raise ValueError("Число дней должно быть положительным")

            end_date = datetime.today()
            start_date = end_date - timedelta(days=days)

            transactions = get_user_transactions(self.user_id, pair[0], pair[1], start_date, end_date)
            if not transactions:
                raise ValueError("Нет транзакций за выбранный период")

            # Подготовка данных для графика
            dates = [t[4] for t in transactions]  # timestamp
            amounts = [t[2] for t in transactions]  # amount

            # Построение графика
            image = self._plot_graph(dates, amounts, pair, "Сумма конвертации")
            self.graph_label.configure(image=ctk.CTkImage(light_image=image, dark_image=image, size=(600, 400)),
                                       text="")

            # Расчет статистики
            total_volume = sum(amounts)
            avg_amount = total_volume / len(amounts) if amounts else 0
            stats_text = (
                f"Объем транзакций: {total_volume:.2f}\n"
                f"Средний объем: {avg_amount:.2f}\n"
                f"Количество операций: {len(amounts)}"
            )
            self.stats_label.configure(text=stats_text)

        except ValueError as e:
            self.graph_label.configure(text=str(e), image=None)
            self.stats_label.configure(text="")

    def _plot_graph(self, dates: list, values: list, pair: list, ylabel: str) -> Image.Image:
        plt.figure(figsize=(10, 5))
        plt.plot(dates, values, marker='o', label=f"{pair[0]}/{pair[1]}")
        plt.title(f"История конвертаций: {pair[0]}/{pair[1]}")
        plt.xlabel("Дата")
        plt.ylabel(ylabel)
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()

        # Добавление интерактивных элементов (масштабирование)
        plt.gca().set_facecolor("#f0f0f0")  # Фон графика
        plt.legend()

        # Сохранение графика в буфер
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        return Image.open(buf)

    def _export_to_csv(self):
        pair = self.pair_var.get().split('/')
        try:
            days = int(self.days_entry.get())
            if days <= 0:
                raise ValueError("Число дней должно быть положительным")

            end_date = datetime.today()
            start_date = end_date - timedelta(days=days)

            transactions = get_user_transactions(self.user_id, pair[0], pair[1], start_date, end_date)
            if not transactions:
                raise ValueError("Нет данных для экспорта")

            # Создание CSV файла
            with open("transactions.csv", "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Дата", "Сумма", "Курс"])
                for t in transactions:
                    writer.writerow([t[4], t[2], t[3]])  # timestamp, amount, rate

            self.stats_label.configure(text="Данные успешно экспортированы в transactions.csv")

        except ValueError as e:
            self.stats_label.configure(text=str(e))

    def _export_graph_to_png(self):
        pair = self.pair_var.get().split('/')
        try:
            days = int(self.days_entry.get())
            if days <= 0:
                raise ValueError("Число дней должно быть положительным")

            end_date = datetime.today()
            start_date = end_date - timedelta(days=days)

            transactions = get_user_transactions(self.user_id, pair[0], pair[1], start_date, end_date)
            if not transactions:
                raise ValueError("Нет данных для экспорта")

            # Подготовка данных для графика
            dates = [t[4] for t in transactions]
            amounts = [t[2] for t in transactions]

            # Построение графика
            image = self._plot_graph(dates, amounts, pair, "Сумма конвертации")

            # Сохранение графика в файл
            image.save("graph.png")
            self.stats_label.configure(text="График успешно экспортирован в graph.png")

        except ValueError as e:
            self.stats_label.configure(text=str(e))

    def _setup_settings_tab(self):
        frame = self.tabview.tab("Настройки")
        frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(frame, text="Язык:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.lang_var = ctk.StringVar(value="ru")
        self.lang_combo = ctk.CTkComboBox(frame, variable=self.lang_var, values=["ru", "en"])
        self.lang_combo.grid(row=0, column=1, sticky="w")

        self.theme_switch = ctk.CTkSwitch(frame, text="Темная тема", command=self._toggle_theme)
        self.theme_switch.grid(row=1, column=0, columnspan=2, pady=10)

        ctk.CTkLabel(frame, text="Порог уведомления (USD/EUR):").grid(row=2, column=0, padx=10, pady=10, sticky="e")
        self.alert_entry = ctk.CTkEntry(frame)
        self.alert_entry.grid(row=2, column=1, sticky="w")

        ctk.CTkButton(frame, text="Сохранить", command=self._save_settings).grid(row=3, column=0, columnspan=2, pady=10)
        self._load_settings()

    def _toggle_theme(self):
        ctk.set_appearance_mode("Dark" if self.theme_switch.get() else "Light")

    def _load_settings(self):
        from database import get_db_connection
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT key, value FROM settings WHERE user_id = ?", (self.user_id,))
            for key, value in c.fetchall():
                if key == 'language':
                    self.lang_var.set(value)
                elif key == 'theme':
                    self.theme_switch.select() if value == "Dark" else self.theme_switch.deselect()
                    ctk.set_appearance_mode(value)
                elif key == 'alert_usd_eur':
                    self.alert_entry.insert(0, value)

    def _save_settings(self):
        from database import get_db_connection
        settings = [
            ('language', self.lang_var.get()),
            ('theme', "Dark" if self.theme_switch.get() else "Light"),
            ('alert_usd_eur', self.alert_entry.get())
        ]
        with get_db_connection() as conn:
            c = conn.cursor()
            for key, value in settings:
                if value:
                    c.execute("INSERT OR REPLACE INTO settings (user_id, key, value) VALUES (?, ?, ?)",
                             (self.user_id, key, value))
            conn.commit()
        self._check_alert()

    def _check_alert(self, current_rate: Optional[float] = None):
        from database import get_db_connection
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE user_id = ? AND key = 'alert_usd_eur'", (self.user_id,))
            alert = c.fetchone()
            if alert:
                try:
                    threshold = float(alert[0])
                    rate = current_rate or (self.rates['USD'] / self.rates['EUR'])
                    if rate < threshold:
                        self.alert_label.configure(text=f"Уведомление: USD/EUR = {rate:.2f} < {threshold}")
                    else:
                        self.alert_label.configure(text="")
                except ValueError:
                    self.alert_label.configure(text="Неверный порог уведомления")

    def _setup_profile_tab(self):
        frame = self.tabview.tab("Профиль")
        frame.grid_columnconfigure(0, weight=1)

        # User Info
        num_transactions, total_exchanged = get_user_stats(self.user_id)
        creation_date = get_user_creation_date(self.user_id)
        ctk.CTkLabel(frame, text=f"Имя пользователя: {self.username}", font=("Arial", 16)).grid(row=0, column=0,
                                                                                                pady=10)
        ctk.CTkLabel(frame, text=f"Дата регистрации: {creation_date}", font=("Arial", 14)).grid(row=1, column=0,
                                                                                                pady=10)
        ctk.CTkLabel(frame, text=f"Всего транзакций: {num_transactions}", font=("Arial", 14)).grid(row=2, column=0,
                                                                                                   pady=10)
        ctk.CTkLabel(frame, text=f"Общая сумма обмена: {total_exchanged:.2f}", font=("Arial", 14)).grid(row=3, column=0,
                                                                                                        pady=10)

        # Last Transactions
        ctk.CTkLabel(frame, text="Последние транзакции:", font=("Arial", 14, "bold")).grid(row=4, column=0, pady=10)
        transactions = get_user_transactions(self.user_id, limit=5)

        # Initialize `i` to a default value
        i = 4  # Start from row 4 (after the "Last Transactions" label)
        for i, (from_curr, to_curr, amount, rate, timestamp) in enumerate(transactions, start=5):
            ctk.CTkLabel(frame, text=f"{timestamp}: {amount:.2f} {from_curr} -> {amount * rate:.2f} {to_curr}",
                         anchor="w").grid(row=i, column=0, pady=5, padx=10, sticky="w")

        # Profile Settings
        # Use `i + 1` to ensure proper placement after the last transaction or the "Last Transactions" label
        ctk.CTkLabel(frame, text="Сменить пароль:", font=("Arial", 14, "bold")).grid(row=i + 1, column=0, pady=10)
        self.new_password_entry = ctk.CTkEntry(frame, placeholder_text="Новый пароль", show="*")
        self.new_password_entry.grid(row=i + 2, column=0, pady=5)
        ctk.CTkButton(frame, text="Обновить пароль", command=self._change_password).grid(row=i + 3, column=0, pady=10)
        self.profile_message = ctk.CTkLabel(frame, text="")
        self.profile_message.grid(row=i + 4, column=0, pady=5)

    def _change_password(self):
        new_password = self.new_password_entry.get()
        if not new_password:
            self.profile_message.configure(text="Введите новый пароль")
            return
        update_user_password(self.user_id, new_password)
        self.profile_message.configure(text="Пароль успешно обновлен")
        self.new_password_entry.delete(0, "end")