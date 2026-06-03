from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from services.invoicing.generator import InvoiceGenerator
from services.operations.event_bus import EventBus, INVOICE_CREATED


class InvoiceService:
    def __init__(self, db):
        self.db = db
        self.generator = InvoiceGenerator()
        self._event_bus = EventBus()

    def generate(self, trip_data: Dict[str, Any], mode: str = "client") -> str:
        return self.generator.generate(trip_data, mode=mode)

    def create_record(self, trip_id: int, inv_number: str, amount: float, due_date: str) -> None:
        self.db.create_invoice_record(trip_id, inv_number, amount, due_date)

    def generate_and_record(self, trip_data: Dict[str, Any], mode: str = "client") -> str:
        path = self.generate(trip_data, mode=mode)
        if mode == "client":
            due_date = (datetime.now() + timedelta(days=30)).strftime("%d/%m/%Y")
            trip_id = trip_data.get("id", 0)
            inv_number = f"INV-{datetime.now().year}-{trip_id:04d}"
            total_price = trip_data.get("total_price_eur", 0) or 0
            self.create_record(
                trip_id=trip_id,
                inv_number=inv_number,
                amount=total_price,
                due_date=due_date,
            )
            self._event_bus.publish(INVOICE_CREATED, {
                "trip_id": trip_id,
                "invoice_number": inv_number,
                "amount": total_price,
                "due_date": due_date,
            })
        return path
