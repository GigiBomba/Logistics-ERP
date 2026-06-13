"""eFTI-compliant eCMR XML generator for Operion ERP.

Produces structured XML conforming to the UN/CEFACT eCMR standard
(EU Regulation 2020/1056 — electronic Freight Transport Information).

Root element: eCMR:eCMR
  eCMR   → urn:un:unece:uncefact:data:standard:eCMR:1
  rsm    → urn:un:unece:uncefact:data:standard:CrossIndustryDocument:1
  ram    → urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:101
  udt    → urn:un:unece:uncefact:data:standard:UnqualifiedDataType:25

CMR boxes mapped to UN/CEFACT elements:
  Box  1  → ram:ShipperTradeParty
  Box  2  → ram:ConsigneeTradeParty
  Box  3  → ram:DeliveryTransportMovement / ram:ArrivalLocation
  Box  4  → ram:DepartureTransportMovement / ram:DepartureLocation
  Box  5  → ram:AttachedTransportDocument
  Box  6  → ram:MainCarriageTransportMovement / ram:CarrierParty
  Box  7  → ram:OnCarriageTransportMovement / ram:CarrierParty  (repeated)
  Box  8  → ram:SpecifiedLogisticsInstruction (reservations)
  Box  9  → ram:IncludedSupplyChainConsignmentItem / ram:PackageQuantity
  Box 10  → ram:IncludedSupplyChainConsignmentItem / ram:Package / ram:TypeCode
  Box 11  → ram:IncludedSupplyChainConsignmentItem / ram:GrossWeightMeasure
  Box 12  → ram:IncludedSupplyChainConsignmentItem / ram:GrossVolumeMeasure
  Box 13  → ram:DeclaredValueForCarriageAmount
  Box 14  → ram:PaymentArrangementCode (distance-based)
  Box 16  → ram:UsedTransportMeans / ram:TransportMeans / ram:RoadTransportEquipment
  Box 17  → ram:AttachedLogisticsTransportEquipment
  Box 18  → ram:SpecifiedLogisticsInstruction (instructions)
  Box 19  → ram:IncludedSupplyChainConsignmentItem / ram:Remarks (special agreements)
  Box 20  → ram:SpecifiedLogisticsPaymentTerms (financial grid)
  Box 21  → rsm:ExchangedDocument (issue place/date)
  Box 22  → rsm:ExchangedDocument / ram:SignatoryDocumentAuthentication (sender)
  Box 23  → rsm:ExchangedDocument / ram:SignatoryDocumentAuthentication (carrier)
  Box 24  → ram:DeliveryNote / ram:SignatoryAuthentication (consignee)
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring, indent, register_namespace

logger = logging.getLogger(__name__)

# ── UN/CEFACT eCMR Namespaces ───────────────────────────────────────
NS_ECMR = "urn:un:unece:uncefact:data:standard:eCMR:1"
NS_RSM  = "urn:un:unece:uncefact:data:standard:CrossIndustryDocument:1"
NS_RAM  = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:101"
NS_UDT  = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:25"
NS_XSI  = "http://www.w3.org/2001/XMLSchema-instance"
XSI_SCHEMA_LOCATION = "urn:un:unece:uncefact:data:standard:eCMR:1 eCMR_1p0.xsd"

# Register namespaces so ElementTree uses our preferred prefixes
register_namespace("eCMR", NS_ECMR)
register_namespace("rsm", NS_RSM)
register_namespace("ram", NS_RAM)
register_namespace("udt", NS_UDT)
register_namespace("xsi", NS_XSI)


# ── Helpers ──────────────────────────────────────────────────────────

def _sub(parent: Element, tag: str, text: Optional[str] = None,
         attrib: Optional[Dict[str, str]] = None) -> Element:
    """Create a SubElement with optional text and attributes."""
    el = SubElement(parent, tag, attrib or {})
    if text is not None and text != "":
        el.text = text
    return el


def _date_string(raw: str) -> str:
    """Convert a date string to YYYYMMDD format (UDT format=102)."""
    if not raw:
        return ""
    # If already a date-like string, try to parse and reformat
    cleaned = raw.strip().replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%m/%d/%Y",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
                "%d.%m.%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned[:19], fmt).strftime("%Y%m%d")
        except (ValueError, IndexError):
            continue
    # Fallback — strip non-digits and take first 8
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return raw


def _date_time_element(parent: Element, tag: str, date_str: str) -> None:
    """Create <tag><udt:DateTimeString format="102">YYYYMMDD</...></...>."""
    if not date_str:
        return
    dt_elem = _sub(parent, tag)
    _sub(dt_elem, "udt:DateTimeString", _date_string(date_str),
         {"format": "102"})


def _party_postal_address(parent: Element, street: str, city: str,
                           postcode: str, country: str) -> None:
    """Build a ram:PostalTradeAddress sub-tree."""
    addr = _sub(parent, "ram:PostalTradeAddress")
    if street:
        _sub(addr, "ram:StreetName", street)
    if city:
        _sub(addr, "ram:CityName", city)
    if postcode:
        _sub(addr, "ram:PostcodeCode", postcode)
    if country:
        _sub(addr, "ram:CountryID", country, {"schemeID": "ISO3166Alpha2"})


def _party_tax_registrations(parent: Element, vat: str = "",
                              eori: str = "") -> None:
    """Add ram:SpecifiedTaxRegistration child elements for VAT / EORI."""
    if vat:
        tax = _sub(parent, "ram:SpecifiedTaxRegistration")
        _sub(tax, "ram:ID", vat, {"schemeID": "VA"})
    if eori:
        tax = _sub(parent, "ram:SpecifiedTaxRegistration")
        _sub(tax, "ram:ID", eori, {"schemeID": "EORI"})


def _build_trade_party(parent: Element, tag: str, name: str,
                       street: str = "", city: str = "",
                       postcode: str = "", country: str = "",
                       vat: str = "", eori: str = "",
                       party_id: str = "") -> None:
    """Build a TradeParty (Shipper, Consignee, Carrier) with optional fields."""
    party = _sub(parent, tag)
    if party_id:
        _sub(party, "ram:ID", party_id)
    if name:
        _sub(party, "ram:Name", name)
    if street or city or postcode or country:
        _party_postal_address(party, street, city, postcode, country)
    _party_tax_registrations(party, vat, eori)


def _build_location(parent: Element, tag: str, country: str = "",
                    city: str = "") -> None:
    """Build a Location element (e.g. DepartureLocation, ArrivalLocation)."""
    loc = _sub(parent, tag)
    if country:
        _sub(loc, "ram:CountryID", country, {"schemeID": "ISO3166Alpha2"})
    if city:
        _sub(loc, "ram:CityName", city)


# ── Main Generator ───────────────────────────────────────────────────

def generate_efti_xml(
    cmr_number: str,
    trip_data: Dict[str, Any],
    company_config: Dict[str, Any],
    client_data: Optional[Dict[str, Any]] = None,
    truck_data: Optional[Dict[str, Any]] = None,
    driver_data: Optional[Dict[str, Any]] = None,
    successive_carriers: Optional[List[Dict[str, Any]]] = None,
    role: str = "consignor",
) -> str:
    """Generate UN/CEFACT eCMR compliant XML.

    Parameters
    ----------
    cmr_number : str
        The CMR document number.
    trip_data : dict
        Trip context dictionary (produced by CMRGenerator._gather_context).
    company_config : dict
        Company configuration (keys: company_name, address, cui,
        eori_number, …).
    client_data : dict or None
        Client data (keys: name, address, vat_number, eori_number, …).
    truck_data : dict or None
        Truck data (keys: plate_number, trailer_plate).
    driver_data : dict or None
        Driver data (keys: name, license_number).
    successive_carriers : list[dict] or None
        List of successive carriers (keys: carrier_name, carrier_address,
        carrier_country, vehicle_plate, driver_name).
    role : str
        ``"consignor"`` (default) — company is the sender / shipper.
        ``"consignee"`` — company is the receiver / consignee.

    Returns
    -------
    str
        Pretty-printed XML string with ``<?xml …?>`` declaration.
    """
    cd = client_data or {}
    vh = truck_data or {}
    dr = driver_data or {}

    # ── Role-based party mapping ─────────────────────────────────────
    if role == "consignee":
        # Company is the receiver (ConsigneeTradeParty)
        shipper_name   = cd.get("name", trip_data.get("consignor_name", ""))
        shipper_addr   = cd.get("address", trip_data.get("consignor_address", ""))
        shipper_country = trip_data.get("loading_country", cd.get("country", ""))
        shipper_city   = trip_data.get("loading_city", cd.get("city", ""))
        shipper_vat    = cd.get("vat_number", trip_data.get("consignor_vat", ""))
        shipper_eori   = cd.get("eori_number", trip_data.get("consignor_eori", ""))

        consignee_name    = company_config.get("company_name", trip_data.get("client_name", ""))
        consignee_addr    = company_config.get("address", trip_data.get("client_address", ""))
        consignee_country = trip_data.get("delivery_country", "")
        consignee_city    = trip_data.get("delivery_city", "")
        consignee_vat     = company_config.get("cui", trip_data.get("consignee_vat", ""))
        consignee_eori    = company_config.get("eori_number", trip_data.get("consignee_eori", ""))
    else:
        # Default: company is the sender / shipper (ShipperTradeParty)
        shipper_name   = company_config.get("company_name", trip_data.get("consignor_name", ""))
        shipper_addr   = company_config.get("address", trip_data.get("consignor_address", ""))
        shipper_country = trip_data.get("loading_country", "")
        shipper_city   = trip_data.get("loading_city", "")
        shipper_vat    = company_config.get("cui", trip_data.get("consignor_vat", ""))
        shipper_eori   = company_config.get("eori_number", trip_data.get("consignor_eori", ""))

        consignee_name    = cd.get("name", trip_data.get("client_name", ""))
        consignee_addr    = cd.get("address", trip_data.get("client_address", ""))
        consignee_country = trip_data.get("delivery_country", cd.get("country", ""))
        consignee_city    = trip_data.get("delivery_city", cd.get("city", ""))
        consignee_vat     = cd.get("vat_number", trip_data.get("consignee_vat", ""))
        consignee_eori    = cd.get("eori_number", trip_data.get("consignee_eori", ""))

    # Carrier always comes from company_config (the transport company)
    carrier_name    = company_config.get("company_name", trip_data.get("carrier_name", ""))
    carrier_addr    = company_config.get("address", trip_data.get("carrier_address", ""))
    carrier_country = trip_data.get("carrier_country", "")
    carrier_city    = trip_data.get("carrier_city", "")
    carrier_vat     = company_config.get("cui", trip_data.get("carrier_vat", ""))
    carrier_eori    = company_config.get("eori_number", trip_data.get("carrier_eori", ""))

    # ── Root element ─────────────────────────────────────────────────
    # NOTE: eCMR/ram/rsm/xsi xmlns are auto-generated by register_namespace;
    # udt must be explicit because it only appears deeper in the tree.
    root = Element(f"{{{NS_ECMR}}}eCMR", {
        "xmlns:udt": NS_UDT,
        f"{{{NS_XSI}}}schemaLocation": XSI_SCHEMA_LOCATION,
    })

    # ── ExchangedDocumentContext ─────────────────────────────────────
    ctx = _sub(root, f"{{{NS_RSM}}}ExchangedDocumentContext")
    ctx_param = _sub(ctx, f"{{{NS_RAM}}}GuidelineSpecifiedDocumentContextParameter")
    _sub(ctx_param, f"{{{NS_RAM}}}ID", "urn:un:unece:uncefact:eCMR:1")

    # ── ExchangedDocument (Box 21 + signature boxes 22, 23) ─────────
    doc = _sub(root, f"{{{NS_RSM}}}ExchangedDocument")
    _sub(doc, f"{{{NS_RAM}}}ID", cmr_number)
    _sub(doc, f"{{{NS_RAM}}}TypeCode", "701",
         {"listID": "UN/ECE 1001"})

    # Issue date/time (Box 21)
    issue_date = trip_data.get("issue_date", trip_data.get("place_of_loading_date",
                               datetime.now().strftime("%Y-%m-%d")))
    _date_time_element(doc, f"{{{NS_RAM}}}IssueDateTime", issue_date)

    # Issue location (Box 21)
    issue_place = trip_data.get("issue_place", trip_data.get("place_of_loading", ""))
    issue_country = trip_data.get("issue_country", trip_data.get("loading_country", ""))
    if issue_place or issue_country:
        issue_loc = _sub(doc, f"{{{NS_RAM}}}IssueLocation")
        if issue_country:
            _sub(issue_loc, f"{{{NS_RAM}}}CountryID", issue_country,
                 {"schemeID": "ISO3166Alpha2"})
        if issue_place:
            _sub(issue_loc, f"{{{NS_RAM}}}CityName", issue_place)

    # Box 22 — Sender signature (in ExchangedDocument)
    sig_sender_path = trip_data.get("sig_sender_path", "")
    if sig_sender_path:
        sig_doc_auth = _sub(doc, f"{{{NS_RAM}}}SignatoryDocumentAuthentication")
        _sub(sig_doc_auth, f"{{{NS_RAM}}}SignatoryAuthentication",
             "presented", {"authenticationTypeCode": "DigitalSignature"})
        _date_time_element(sig_doc_auth, f"{{{NS_RAM}}}AuthenticationDateTime", issue_date)

    # Box 23 — Carrier signature (in ExchangedDocument)
    sig_carrier_path = trip_data.get("sig_carrier_path", "")
    if sig_carrier_path:
        sig_doc_auth = _sub(doc, f"{{{NS_RAM}}}SignatoryDocumentAuthentication")
        _sub(sig_doc_auth, f"{{{NS_RAM}}}SignatoryAuthentication",
             "presented", {"authenticationTypeCode": "DigitalSignature"})
        _date_time_element(sig_doc_auth, f"{{{NS_RAM}}}AuthenticationDateTime",
                           datetime.now().strftime("%Y-%m-%d"))

    # ── SpecifiedSupplyChainConsignment ──────────────────────────────
    cons = _sub(root, f"{{{NS_RAM}}}SpecifiedSupplyChainConsignment")
    _sub(cons, f"{{{NS_RAM}}}ID", cmr_number)

    # ── Box 1 — Consignor (ShipperTradeParty) ────────────────────────
    _build_trade_party(
        cons, f"{{{NS_RAM}}}ShipperTradeParty",
        name=shipper_name,
        street=shipper_addr,
        city=shipper_city,
        country=shipper_country,
        vat=shipper_vat,
        eori=shipper_eori,
        party_id=trip_data.get("consignor_id", ""),
    )

    # ── Box 2 — Consignee (ConsigneeTradeParty) ─────────────────────
    _build_trade_party(
        cons, f"{{{NS_RAM}}}ConsigneeTradeParty",
        name=consignee_name,
        street=consignee_addr,
        city=consignee_city,
        country=consignee_country,
        vat=consignee_vat,
        eori=consignee_eori,
        party_id=trip_data.get("consignee_id", cd.get("id", "")),
    )

    # ── Box 4 — Place & Date of Taking Over (DepartureTransportMovement) ─
    dept = _sub(cons, f"{{{NS_RAM}}}DepartureTransportMovement")
    loading_place = trip_data.get("place_of_loading",
                    trip_data.get("origin", trip_data.get("loading_address", "")))
    loading_city = trip_data.get("loading_city", "")
    loading_country = trip_data.get("loading_country", "")
    if loading_city or loading_country:
        _build_location(dept, f"{{{NS_RAM}}}DepartureLocation",
                        country=loading_country, city=loading_city or loading_place)
    elif loading_place:
        _build_location(dept, f"{{{NS_RAM}}}DepartureLocation",
                        city=loading_place)
    loading_date = trip_data.get("place_of_loading_date", "")
    _date_time_element(dept, f"{{{NS_RAM}}}PlannedDepartureDateTime", loading_date)

    # ── Box 3 — Place of Delivery (DeliveryTransportMovement) ────────
    delv = _sub(cons, f"{{{NS_RAM}}}DeliveryTransportMovement")
    delivery_place = trip_data.get("place_of_delivery",
                     trip_data.get("destination", trip_data.get("unloading_address", "")))
    delivery_city = trip_data.get("delivery_city", "")
    delivery_country = trip_data.get("delivery_country", "")
    if delivery_city or delivery_country:
        _build_location(delv, f"{{{NS_RAM}}}ArrivalLocation",
                        country=delivery_country, city=delivery_city or delivery_place)
    elif delivery_place:
        _build_location(delv, f"{{{NS_RAM}}}ArrivalLocation",
                        city=delivery_place)

    # ── Box 5 — Documents Attached ───────────────────────────────────
    docs_raw = trip_data.get("documents_attached", "")
    if docs_raw:
        # Split comma-separated list into individual documents
        doc_refs = [d.strip() for d in docs_raw.split(",") if d.strip()]
        for ref in doc_refs:
            att_doc = _sub(cons, f"{{{NS_RAM}}}AttachedTransportDocument")
            _sub(att_doc, f"{{{NS_RAM}}}TypeCode", "916",
                 {"listID": "UN/ECE 1001"})
            _sub(att_doc, f"{{{NS_RAM}}}ID", ref)

    # ── Box 6 — Carrier (MainCarriageTransportMovement) ─────────────
    main_carr = _sub(cons, f"{{{NS_RAM}}}MainCarriageTransportMovement")
    _build_trade_party(
        main_carr, f"{{{NS_RAM}}}CarrierParty",
        name=carrier_name,
        street=carrier_addr,
        city=carrier_city,
        country=carrier_country,
        vat=carrier_vat,
        eori=carrier_eori,
        party_id=trip_data.get("carrier_id", ""),
    )

    # ── Box 7 — Successive Carriers (OnCarriageTransportMovement) ────
    succ_carriers = successive_carriers or trip_data.get("successive_carriers", [])
    for sc in succ_carriers:
        on_carr = _sub(cons, f"{{{NS_RAM}}}OnCarriageTransportMovement")
        _build_trade_party(
            on_carr, f"{{{NS_RAM}}}CarrierParty",
            name=sc.get("carrier_name", ""),
            street=sc.get("carrier_address", ""),
            city=sc.get("carrier_city", ""),
            country=sc.get("carrier_country", ""),
            vat=sc.get("carrier_vat", ""),
            party_id=sc.get("carrier_id", ""),
        )
        # Vehicle plate for successive carrier
        sc_plate = sc.get("vehicle_plate", "")
        if sc_plate:
            used_means = _sub(on_carr, f"{{{NS_RAM}}}UsedTransportMeans")
            means = _sub(used_means, f"{{{NS_RAM}}}TransportMeans")
            road_equip = _sub(means, f"{{{NS_RAM}}}RoadTransportEquipment")
            _sub(road_equip, f"{{{NS_RAM}}}LicensePlateID", sc_plate)
        # Driver for successive carrier
        sc_driver = sc.get("driver_name", "")
        if sc_driver:
            driver = _sub(on_carr, f"{{{NS_RAM}}}SpecifiedTransportPerson")
            _sub(driver, f"{{{NS_RAM}}}Name", sc_driver)

    # ── Box 8 — Carrier's Reservations ──────────────────────────────
    reservations = trip_data.get("carrier_reservations", "")
    if reservations:
        instr = _sub(cons, f"{{{NS_RAM}}}SpecifiedLogisticsInstruction")
        _sub(instr, f"{{{NS_RAM}}}Description", reservations)

    # ── Boxes 9-12 — Goods (IncludedSupplyChainConsignmentItem) ─────
    item = _sub(cons, f"{{{NS_RAM}}}IncludedSupplyChainConsignmentItem")
    _sub(item, f"{{{NS_RAM}}}SequenceNumeric", "1")

    # Package quantity (Box 9)
    pkg_count = trip_data.get("package_count", "")
    if pkg_count:
        _sub(item, f"{{{NS_RAM}}}PackageQuantity", str(pkg_count),
             {"unitCode": "PCE"})

    # Package type and marks (Box 10)
    pkg_type = trip_data.get("package_type", "")
    cargo_marks = trip_data.get("cargo_marks", trip_data.get("marks", ""))
    if pkg_type or cargo_marks:
        pkg = _sub(item, f"{{{NS_RAM}}}Package")
        if pkg_type:
            _sub(pkg, f"{{{NS_RAM}}}TypeCode", pkg_type)
        if cargo_marks:
            _sub(pkg, f"{{{NS_RAM}}}Marking", cargo_marks)

    # Nature of goods / description (Box 9 part)
    cargo_desc = trip_data.get("cargo_description", "")
    if cargo_desc:
        _sub(item, f"{{{NS_RAM}}}SummaryDescription", cargo_desc)

    # HS code (Box 10 part)
    hs_code = trip_data.get("hs_code", "")
    if hs_code:
        cc = _sub(item, f"{{{NS_RAM}}}CommodityCode")
        _sub(cc, f"{{{NS_RAM}}}ValueCode", hs_code)

    # Gross weight (Box 11)
    gross_wt = trip_data.get("gross_weight_kg", "")
    if gross_wt:
        _sub(item, f"{{{NS_RAM}}}GrossWeightMeasure", str(gross_wt),
             {"unitCode": "KGM"})

    # Gross volume (Box 12)
    volume = trip_data.get("volume_m3", "")
    if volume:
        _sub(item, f"{{{NS_RAM}}}GrossVolumeMeasure", str(volume),
             {"unitCode": "MTQ"})

    # ── Box 13 — Freight Charges (Declared Value for Carriage) ──────
    cod_amount = trip_data.get("cod_amount", "")
    freight_charges = trip_data.get("freight_charges", cod_amount)
    if freight_charges:
        try:
            val = float(freight_charges)
            _sub(cons, f"{{{NS_RAM}}}DeclaredValueForCarriageAmount",
                 f"{val:.2f}", {"currencyID": "EUR"})
        except (ValueError, TypeError):
            pass

    # ── Box 14 — Payment Terms / Distance ────────────────────────────
    distance = trip_data.get("distance_km", "")
    carriage_payer = trip_data.get("carriage_payer", "")
    if distance or carriage_payer:
        terms_text = ""
        if carriage_payer:
            terms_text += f"Payer: {carriage_payer}"
        if distance:
            try:
                terms_text += f" Distance: {round(float(distance), 1)} km"
            except (ValueError, TypeError):
                terms_text += f" Distance: {distance} km"
        _sub(cons, f"{{{NS_RAM}}}PaymentArrangementCode", terms_text.strip())

    # ── Box 16 — Vehicle (Transport Means) ──────────────────────────
    veh_plate = vh.get("plate_number", trip_data.get("truck_plate",
                            trip_data.get("truck_number", "")))
    if veh_plate:
        used_means = _sub(cons, f"{{{NS_RAM}}}UsedTransportMeans")
        means = _sub(used_means, f"{{{NS_RAM}}}TransportMeans")
        road_equip = _sub(means, f"{{{NS_RAM}}}RoadTransportEquipment")
        _sub(road_equip, f"{{{NS_RAM}}}LicensePlateID", veh_plate)

    # ── Box 17 — Trailer ────────────────────────────────────────────
    trailer_plate = vh.get("trailer_plate", trip_data.get("trailer_plate", ""))
    if trailer_plate:
        trailer_eq = _sub(cons, f"{{{NS_RAM}}}AttachedLogisticsTransportEquipment")
        _sub(trailer_eq, f"{{{NS_RAM}}}ID", trailer_plate)

    # ── Driver ───────────────────────────────────────────────────────
    driver_name = dr.get("name", trip_data.get("driver_name", ""))
    if driver_name:
        driver = _sub(cons, f"{{{NS_RAM}}}SpecifiedTransportPerson")
        _sub(driver, f"{{{NS_RAM}}}Name", driver_name)
        lic = dr.get("license_number", trip_data.get("driver_license", ""))
        if lic:
            _sub(driver, f"{{{NS_RAM}}}ID", lic)

    # ── Box 18 — Special Instructions ────────────────────────────────
    instructions = trip_data.get("carrier_instructions", "")
    if instructions:
        instr = _sub(cons, f"{{{NS_RAM}}}SpecifiedLogisticsInstruction")
        _sub(instr, f"{{{NS_RAM}}}Description", instructions)

    # ── Box 19 — Special Agreements ──────────────────────────────────
    special_agreements = trip_data.get("special_agreements", "")
    if special_agreements:
        # Use Remarks-like element; attach to consignment item or a dedicated element
        _sub(item, f"{{{NS_RAM}}}Remarks", special_agreements)

    # ── Box 20 — Financial Grid (payment terms breakdown) ────────────
    fin_grid = trip_data.get("financial_grid", {})
    if isinstance(fin_grid, dict) and any(v for v in fin_grid.values() if v):
        payer_val = 1 if str(carriage_payer).lower() == "consignee" else 0
        _sub(cons, f"{{{NS_RAM}}}FreightPaymentTermCode", str(payer_val),
             {"listID": "UN/ECE 2001"})

    # ── Dangerous Goods (ADR) ────────────────────────────────────────
    adr_raw = trip_data.get("adr_info_json")
    if adr_raw:
        try:
            if isinstance(adr_raw, str):
                adr_items = json.loads(adr_raw)
            else:
                adr_items = adr_raw
            if isinstance(adr_items, list):
                for adr in adr_items:
                    dg = _sub(cons, f"{{{NS_RAM}}}IncludedDangerousGoods")
                    un_no = adr.get("un_no", "")
                    if un_no:
                        _sub(dg, f"{{{NS_RAM}}}UNDGIdentifier", str(un_no))
                    adr_class = adr.get("adr_class", "")
                    if adr_class:
                        _sub(dg, f"{{{NS_RAM}}}ClassificationCode", str(adr_class))
                    pack_grp = adr.get("packing_group", "")
                    if pack_grp:
                        _sub(dg, f"{{{NS_RAM}}}PackingGroupCode", str(pack_grp))
                    tunnel = adr.get("tunnel_code", "")
                    if tunnel:
                        _sub(dg, f"{{{NS_RAM}}}TunnelRestrictionCode", str(tunnel))
                    qty = adr.get("quantity", "")
                    if qty:
                        _sub(dg, f"{{{NS_RAM}}}GrossMassMeasure", str(qty),
                             {"unitCode": "KGM"})
        except (json.JSONDecodeError, TypeError) as exc:
            logger.debug("ADR XML generation skipped: %s", exc)

    # ── Box 24 — Consignee Signature (DeliveryNote) ─────────────────
    sig_consignee_path = trip_data.get("sig_consignee_path", "")
    if sig_consignee_path:
        del_note = _sub(cons, f"{{{NS_RAM}}}DeliveryNote")
        _sub(del_note, f"{{{NS_RAM}}}SignatoryAuthentication",
             "presented", {"authenticationTypeCode": "DigitalSignature"})

    # ── Signatures (one SpecifiedSignature per party) ────────────────
    sig_statuses = {
        "sender": "unsigned",
        "carrier": "unsigned",
        "consignee": "unsigned",
    }
    if sig_sender_path:
        sig_statuses["sender"] = "signed"
    if sig_carrier_path:
        sig_statuses["carrier"] = "signed"
    if sig_consignee_path:
        sig_statuses["consignee"] = "signed"

    for party in ("sender", "carrier", "consignee"):
        spec_sig = _sub(root, f"{{{NS_RSM}}}SpecifiedSignature")
        _sub(spec_sig, f"{{{NS_RAM}}}TypeCode", party)
        _sub(spec_sig, f"{{{NS_RAM}}}StatusCode", sig_statuses[party])

    # ── Serialize ────────────────────────────────────────────────────
    indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode")
