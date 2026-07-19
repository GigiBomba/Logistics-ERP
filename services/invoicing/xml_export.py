"""Deterministic XML export for Romanian-compliant invoices.

This module produces UBL-inspired invoice XML that is:

- Locale-independent (always UTC, invariant decimal format)
- UTF-8 encoded
- Schema-stable (field names and structure won't change between releases)
- Capable of becoming a full UBL e-Factura generator without changing the invoice domain

The export layer reads from the typed ``InvoiceResult`` model only — it does
not depend on the database schema or ORM internals.

Usage::

    from services.invoicing.xml_export import InvoiceXmlExport
    from models.invoice_models import InvoiceResult

    exporter = InvoiceXmlExport(
        seller_name="SC TRANSPORT SRL",
        seller_cui="RO12345678",
        seller_reg="J12/345/2024",
        seller_address="Str. Principala nr. 10",
        seller_county="Cluj",
        seller_city="Cluj-Napoca",
        seller_country="RO",
        seller_iban="RO12AAAA12345678901234",
        seller_bank_name="BCR",
        seller_email="office@transport.ro",
        seller_phone="+40 123 456 789",
    )
    xml_bytes = exporter.export(invoice_result)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from models.invoice_models import InvoiceResult


# ── Helpers ──────────────────────────────────────────────────────────────

def _d(val: Any) -> str:
    """Format a number as a locale-independent decimal string with 2 decimals.

    ``None`` and non-numeric values become ``"0.00"``.
    """
    if val is None:
        return "0.00"
    try:
        d = Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return str(d)
    except (ValueError, TypeError, ArithmeticError):
        return "0.00"


def _dt(val: Any) -> str:
    """Format a date/datetime as ISO-8601 date string (YYYY-MM-DD)."""
    if val is None:
        return ""
    if isinstance(val, (date, datetime)):
        return val.isoformat()
    if isinstance(val, str):
        # Strip time portion if present
        return val[:10]
    return str(val)[:10]


def _txt(val: Any) -> str:
    """Return a safe string, stripping None to empty."""
    return str(val).strip() if val is not None else ""


# ── Seller Data ──────────────────────────────────────────────────────────


class SellerData:
    """Structured seller information for XML export."""

    def __init__(
        self,
        name: str = "",
        cui: str = "",
        reg_number: str = "",
        address: str = "",
        county: str = "",
        city: str = "",
        country: str = "RO",
        iban: str = "",
        bank_name: str = "",
        email: str = "",
        phone: str = "",
    ):
        self.name = name
        self.cui = cui
        self.reg_number = reg_number
        self.address = address
        self.county = county
        self.city = city
        self.country = country
        self.iban = iban
        self.bank_name = bank_name
        self.email = email
        self.phone = phone

    @classmethod
    def from_company_config(cls, config: dict) -> SellerData:
        """Build from the company config dict returned by ``load_company_config()``."""
        return cls(
            name=config.get("company_name", ""),
            cui=config.get("cui", ""),
            reg_number=config.get("reg_number", ""),
            address=config.get("address", ""),
            county=config.get("county", ""),
            city=config.get("city", ""),
            country=config.get("country", "RO"),
            iban=config.get("iban", ""),
            bank_name=config.get("bank_name", ""),
            email=config.get("email", ""),
            phone=config.get("phone", ""),
        )


# ── Exporter ─────────────────────────────────────────────────────────────


class InvoiceXmlExport:
    """Deterministic invoice → XML exporter.

    Produces a UBL-inspired XML structure that can be mapped to
    the Romanian e-Factura CIUS-RO format with minimal transformation.

    Thread-safe: does not maintain mutable state between calls.
    """

    NS = {
        "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }

    def __init__(self, seller: SellerData):
        self.seller = seller

    # ── Public API ───────────────────────────────────────────────────────

    def export(self, invoice: InvoiceResult) -> bytes:
        """Return a UTF-8 encoded XML string for *invoice*.

        The output is deterministic: the same input always produces
        the same byte output.
        """
        root = self._build(invoice)
        xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
        # Prepend declaration manually for full control
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            + xml_str
        ).encode("utf-8")

    def export_to_file(self, invoice: InvoiceResult, file_path: str) -> str:
        """Write the XML export to *file_path* and return the path."""
        data = self.export(invoice)
        with open(file_path, "wb") as f:
            f.write(data)
        return file_path

    # ── Internal ─────────────────────────────────────────────────────────

    def _build(self, invoice: InvoiceResult) -> ET.Element:
        root = ET.Element("Invoice", attrib={
            "xmlns": self.NS[""],
            "xmlns:cac": self.NS["cac"],
            "xmlns:cbc": self.NS["cbc"],
        })

        # ── UBL identifiers ──────────────────────────────────────────
        self._add(root, "cbc:UBLVersionID", "2.1")
        self._add(root, "cbc:CustomizationID", "ROMANIAN_EFACTURA_CIUS_RO")
        self._add(root, "cbc:ID", invoice.invoice_number)
        self._add(root, "cbc:IssueDate", _dt(invoice.invoice_date))
        self._add(root, "cbc:DueDate", _dt(invoice.due_date))
        self._add(root, "cbc:InvoiceTypeCode", invoice.invoice_type)
        self._add(root, "cbc:DocumentCurrencyCode", invoice.currency)
        if invoice.exchange_rate != 1.0:
            self._add(root, "cbc:TaxCurrencyCode", "RON")
            self._add(root, "cbc:CalculationRate", _d(invoice.exchange_rate))

        # ── Notes ────────────────────────────────────────────────────
        if invoice.notes:
            self._add(root, "cbc:Note", invoice.notes)

        # ── Accounting / Period ──────────────────────────────────────
        period = self._sub(root, "cac:InvoicePeriod")
        self._add(period, "cbc:StartDate", _dt(invoice.invoice_date))
        self._add(period, "cbc:EndDate", _dt(invoice.due_date))

        # ── Seller (AccountingSupplier) ──────────────────────────────
        seller_party = self._sub(root, "cac:AccountingSupplierParty")
        seller_p = self._sub(seller_party, "cac:Party")
        self._add(seller_p, "cbc:EndpointID", self.seller.cui,
                  attrib={"schemeID": "CUI"})
        seller_name_e = self._sub(seller_p, "cac:PartyName")
        self._add(seller_name_e, "cbc:Name", self.seller.name)

        seller_addr = self._sub(seller_p, "cac:PostalAddress")
        self._add(seller_addr, "cbc:CityName", self.seller.city)
        self._add(seller_addr, "cbc:CountrySubentity", self.seller.county)
        self._add(seller_addr, "cbc:AddressLine", self.seller.address)

        seller_country = self._sub(seller_addr, "cac:Country")
        self._add(seller_country, "cbc:IdentificationCode", self.seller.country)

        seller_contact = self._sub(seller_p, "cac:Contact")
        self._add(seller_contact, "cbc:ElectronicMail", self.seller.email)
        self._add(seller_contact, "cbc:Telephone", self.seller.phone)

        # Seller legal registration
        seller_reg = self._sub(seller_p, "cac:PartyLegalEntity")
        self._add(seller_reg, "cbc:RegistrationName", self.seller.name)
        self._add(seller_reg, "cbc:CompanyID", self.seller.cui,
                  attrib={"schemeID": "CUI"})
        self._add(seller_reg, "cbc:CompanyLegalForm", self.seller.reg_number)

        # Seller financial account (IBAN)
        if self.seller.iban:
            fin_acc = self._sub(seller_party, "cac:FinancialAccount")
            self._add(fin_acc, "cbc:ID", self.seller.iban)
            if self.seller.bank_name:
                self._add(fin_acc, "cbc:Name", self.seller.bank_name)

        # ── Buyer (AccountingCustomer) ───────────────────────────────
        buyer_party = self._sub(root, "cac:AccountingCustomerParty")
        buyer_p = self._sub(buyer_party, "cac:Party")

        # Resolve buyer info from invoice (client data passed separately)
        buyer_name = getattr(invoice, "_buyer_name", "") or ""
        buyer_cui = getattr(invoice, "_buyer_cui", "") or ""
        buyer_address = getattr(invoice, "_buyer_address", "") or ""
        buyer_county = getattr(invoice, "_buyer_county", "") or ""
        buyer_city = getattr(invoice, "_buyer_city", "") or ""
        buyer_country = getattr(invoice, "_buyer_country", "") or "RO"
        buyer_email = getattr(invoice, "_buyer_email", "") or ""

        if buyer_cui:
            self._add(buyer_p, "cbc:EndpointID", buyer_cui,
                      attrib={"schemeID": "CUI"})

        if buyer_name:
            buyer_name_e = self._sub(buyer_p, "cac:PartyName")
            self._add(buyer_name_e, "cbc:Name", buyer_name)

        buyer_addr = self._sub(buyer_p, "cac:PostalAddress")
        if buyer_city:
            self._add(buyer_addr, "cbc:CityName", buyer_city)
        if buyer_county:
            self._add(buyer_addr, "cbc:CountrySubentity", buyer_county)
        buyer_addr_line = ", ".join(filter(None, [buyer_address]))
        if buyer_addr_line:
            self._add(buyer_addr, "cbc:AddressLine", buyer_addr_line)

        b_country = self._sub(buyer_addr, "cac:Country")
        self._add(b_country, "cbc:IdentificationCode", buyer_country)

        if buyer_email:
            b_contact = self._sub(buyer_p, "cac:Contact")
            self._add(b_contact, "cbc:ElectronicMail", buyer_email)

        buyer_legal = self._sub(buyer_p, "cac:PartyLegalEntity")
        if buyer_name:
            self._add(buyer_legal, "cbc:RegistrationName", buyer_name)
        if buyer_cui:
            self._add(buyer_legal, "cbc:CompanyID", buyer_cui,
                      attrib={"schemeID": "CUI"})

        # ── Tax totals ───────────────────────────────────────────────
        tax_total = self._sub(root, "cac:TaxTotal")
        self._add(tax_total, "cbc:TaxAmount", _d(invoice.total_vat),
                  attrib={"currencyID": invoice.currency})

        # ── Monetary totals ──────────────────────────────────────────
        legal_total = self._sub(root, "cac:LegalMonetaryTotal")
        self._add(legal_total, "cbc:LineExtensionAmount", _d(invoice.subtotal_net),
                  attrib={"currencyID": invoice.currency})
        self._add(legal_total, "cbc:TaxExclusiveAmount", _d(invoice.subtotal_net),
                  attrib={"currencyID": invoice.currency})
        self._add(legal_total, "cbc:TaxInclusiveAmount", _d(invoice.total_gross),
                  attrib={"currencyID": invoice.currency})
        self._add(legal_total, "cbc:PayableAmount", _d(invoice.total_gross),
                  attrib={"currencyID": invoice.currency})
        if invoice.amount_paid > 0:
            self._add(legal_total, "cbc:PaidAmount", _d(invoice.amount_paid),
                      attrib={"currencyID": invoice.currency})

        # ── Invoice lines ────────────────────────────────────────────
        for line in invoice.line_items:
            self._add_line(root, line, invoice.currency)

        return root

    def _add_line(self, root: ET.Element, line, currency: str) -> None:
        """Add a single ``InvoiceLine`` element."""
        line_elem = self._sub(root, "cac:InvoiceLine")

        # Line ID (sequential — use index at call site if needed)
        line_id = getattr(line, "_line_id", 1)
        self._add(line_elem, "cbc:ID", str(line_id))

        # Quantity
        qty = float(line.quantity or 1.0)
        uom = line.unit_of_measure or "buc"
        self._add(line_elem, "cbc:InvoicedQuantity", _d(qty),
                  attrib={"unitCode": uom})

        # Line extension amount (taxable amount)
        taxable = line.taxable_amount or 0.0
        self._add(line_elem, "cbc:LineExtensionAmount", _d(taxable),
                  attrib={"currencyID": currency})

        # Item
        item = self._sub(line_elem, "cac:Item")
        self._add(item, "cbc:Name", line.description)

        # Price
        price = self._sub(line_elem, "cac:Price")
        unit_price = float(line.unit_price or 0.0)
        self._add(price, "cbc:PriceAmount", _d(unit_price),
                  attrib={"currencyID": currency})

        # Discount
        discount = float(line.discount_amount or 0.0)
        if discount > 0:
            allowance = self._sub(line_elem, "cac:AllowanceCharge")
            self._add(allowance, "cbc:ChargeIndicator", "false")
            self._add(allowance, "cbc:Amount", _d(discount),
                      attrib={"currencyID": currency})

        # Tax category
        vat_rate = float(line.vat_rate or 0.0)
        vat_amount = float(line.vat_amount or 0.0)
        tax_total_line = self._sub(line_elem, "cac:TaxTotal")
        self._add(tax_total_line, "cbc:TaxAmount", _d(vat_amount),
                  attrib={"currencyID": currency})

        tax_subtotal = self._sub(tax_total_line, "cac:TaxSubtotal")
        self._add(tax_subtotal, "cbc:TaxableAmount", _d(taxable),
                  attrib={"currencyID": currency})
        self._add(tax_subtotal, "cbc:TaxAmount", _d(vat_amount),
                  attrib={"currencyID": currency})

        tax_category = self._sub(tax_subtotal, "cac:TaxCategory")
        self._add(tax_category, "cbc:ID", self._vat_category_code(vat_rate))
        self._add(tax_category, "cbc:Percent", _d(vat_rate))

        tax_scheme = self._sub(tax_category, "cac:TaxScheme")
        self._add(tax_scheme, "cbc:ID", "VAT")
        self._add(tax_scheme, "cbc:Name", "TVA")

    @staticmethod
    def _vat_category_code(rate: float) -> str:
        """Map Romanian VAT rate to standard category code."""
        if rate == 0:
            return "E"  # Exempt
        elif rate < 5:
            return "Z"  # Zero rated
        elif rate < 10:
            return "S"  # Reduced rate (5%)
        elif rate < 15:
            return "AA"  # Reduced rate (9%)
        else:
            return "S"  # Standard rate (19%)

    # ── XML helpers ──────────────────────────────────────────────────

    @staticmethod
    def _add(parent: ET.Element, tag: str, text: str,
             attrib: Optional[dict] = None) -> ET.Element:
        """Add a simple text child element."""
        elem = ET.SubElement(parent, tag)
        if attrib:
            elem.attrib.update(attrib)
        elem.text = text
        return elem

    @staticmethod
    def _sub(parent: ET.Element, tag: str) -> ET.Element:
        """Add an empty child element and return it."""
        return ET.SubElement(parent, tag)
