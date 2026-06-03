from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Driver:
    id: int
    name: str = ""
    phone: str = ""
    email: str = ""
    license_number: str = ""
    license_category: str = ""
    license_expiry: Optional[str] = None
    medical_expiry: Optional[str] = None
    hire_date: str = ""
    monthly_salary: float = 0.0
    notes: str = ""
    is_active: int = 1
    created_at: str = ""
    updated_at: str = ""

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Driver":
        return Driver(
            id=int(d.get("id", 0)),
            name=str(d.get("name", "")),
            phone=str(d.get("phone", "")),
            email=str(d.get("email", "")),
            license_number=str(d.get("license_number", "")),
            license_category=str(d.get("license_category", "")),
            license_expiry=str(d["license_expiry"]) if d.get("license_expiry") else None,
            medical_expiry=str(d["medical_expiry"]) if d.get("medical_expiry") else None,
            hire_date=str(d.get("hire_date", "")),
            monthly_salary=float(d.get("monthly_salary") or 0),
            notes=str(d.get("notes", "")),
            is_active=int(d.get("is_active", 1)),
            created_at=str(d.get("created_at", "")),
            updated_at=str(d.get("updated_at", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "license_number": self.license_number,
            "license_category": self.license_category,
            "license_expiry": self.license_expiry,
            "medical_expiry": self.medical_expiry,
            "hire_date": self.hire_date,
            "monthly_salary": self.monthly_salary,
            "notes": self.notes,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
