from typing import Any, Dict, List, Optional


class AnalyticsService:
    def __init__(self, db):
        self.db = db

    def get_data(self) -> tuple:
        return self.db.get_analytics_data()
