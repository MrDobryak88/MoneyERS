from ui import LoginWindow
from database import init_db
from api_service import update_historical_rates

if __name__ == "__main__":
    init_db()
    update_historical_rates()
    app = LoginWindow()
    app.mainloop()
