"""eFTI-compliant eCMR XML generator for Operion ERP.

Produces structured XML conforming to UN/CEFACT MMT-RDM patterns
for electronic CMR under EU Regulation 2020/1056.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

logger = logging.getLogger(__name__)

NS_EFTI = "urn:unece:uncefact:transport:efti:1"
NS_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"


def _sub(parent: Element, tag: str, text: Optional[str] = None, attrib: Optional[Dict[str, str]] = None) -> Element:
    el = SubElement(parent, tag, attrib or {})
    if text is not None:
        el.text = text
    return el


def generate_efti_xml(
    cmr_number: str,
    trip_data: Dict[str, Any],
    company_config: Dict[str, Any],
    client_data: Optional[Dict[str, Any]] = None,
    truck_data: Optional[Dict[str, Any]] = None,
    driver_data: Optional[Dict[str, Any]] = None,
    successive_carriers: Optional[List[Dict[str, Any]]] = None,
) -> str:
    root = Element("ConsignmentNote", {
        "xmlns:eFTI": NS_EFTI,
        "xmlns:ram": NS_RAM,
    })

    _sub(root, "ID", cmr_number)
    _sub(root, "IssueDateTime", datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    _sub(root, "ConsignmentReference", f"TRIP-{trip_data.get('trip_id', trip_data.get('id', '0'))}")

    consignor = _sub(root, "Consignor")
    _sub(consignor, "ram:Name", company_config.get("company_name", ""))
    addr1 = _sub(consignor, "ram:PostalAddress")
    _sub(addr1, "ram:LineOne", company_config.get("address", ""))
    _sub(addr1, "ram:CountryID", trip_data.get("loading_country", ""))
    tax1 = _sub(consignor, "ram:SpecifiedTaxRegistration")
    _sub(tax1, "ram:ID", company_config.get("cui", ""), {"schemeID": "VA"})
    eori_val = company_config.get("eori_number", company_config.get("cui", ""))
    if eori_val:
        tax2 = _sub(consignor, "ram:SpecifiedTaxRegistration")
        _sub(tax2, "ram:ID", eori_val, {"schemeID": "EORI"})

    consignee = _sub(root, "Consignee")
    client_name = trip_data.get("client_name", "")
    client_addr = trip_data.get("client_address", "")
    if client_data:
        client_name = client_data.get("name", client_name)
        client_addr = client_data.get("address", client_addr)
    _sub(consignee, "ram:Name", client_name)
    addr2 = _sub(consignee, "ram:PostalAddress")
    _sub(addr2, "ram:LineOne", client_addr)
    _sub(addr2, "ram:CountryID", trip_data.get("delivery_country", ""))
    if client_data and client_data.get("vat_number"):
        tax3 = _sub(consignee, "ram:SpecifiedTaxRegistration")
        _sub(tax3, "ram:ID", client_data["vat_number"], {"schemeID": "VA"})

    carrier = _sub(root, "Carrier")
    _sub(carrier, "ram:Name", company_config.get("company_name", ""))
    _sub(carrier, "ram:ID", company_config.get("cui", ""))
    veh = _sub(carrier, "ram:SpecifiedTransportMeans")
    _sub(veh, "ram:ID", trip_data.get("truck_number", trip_data.get("truck_plate", "")))

    takeover = _sub(root, "TransportSettingTakeOver")
    loc1 = _sub(takeover, "ram:ActualLocation")
    _sub(loc1, "ram:Name", trip_data.get("place_of_loading",
             trip_data.get("origin", trip_data.get("loading_address", ""))))
    _sub(loc1, "ram:CountryID", trip_data.get("loading_country", ""))
    if trip_data.get("place_of_loading_date"):
        _sub(takeover, "ram:EffectiveDateTime",
             trip_data["place_of_loading_date"] + "T00:00:00Z")

    delivery = _sub(root, "TransportSettingDelivery")
    loc2 = _sub(delivery, "ram:ActualLocation")
    _sub(loc2, "ram:Name", trip_data.get("destination",
             trip_data.get("unloading_address", "")))
    _sub(loc2, "ram:CountryID", trip_data.get("delivery_country", ""))

    item = _sub(root, "IncludedConsignmentItem")
    if trip_data.get("gross_weight_kg"):
        _sub(item, "ram:GrossWeight",
             str(trip_data["gross_weight_kg"]), {"measureUnitCode": "KGM"})
    if trip_data.get("volume_m3"):
        _sub(item, "ram:GrossVolume",
             str(trip_data["volume_m3"]), {"measureUnitCode": "MTQ"})
    if trip_data.get("package_count"):
        _sub(item, "ram:TotalTransportPackagesQuantity",
             str(trip_data["package_count"]))
    _sub(item, "ram:Description", trip_data.get("cargo_description", ""))

    if trip_data.get("carrier_instructions"):
        remarks = _sub(root, "Remarks")
        _sub(remarks, "eFTI:SenderInstructions", trip_data["carrier_instructions"])
    if trip_data.get("carrier_reservations"):
        if not trip_data.get("carrier_instructions"):
            remarks = _sub(root, "Remarks")
        _sub(remarks, "eFTI:CarrierReservations", trip_data["carrier_reservations"])

    if trip_data.get("adr_info_json"):
        try:
            adr_items = json.loads(trip_data["adr_info_json"])
            for adr in adr_items:
                dg = _sub(root, "DangerousGoods")
                _sub(dg, "ram:UNDGIdentifier", adr.get("un_no", ""))
                _sub(dg, "ram:ClassificationCode", adr.get("adr_class", ""))
                _sub(dg, "ram:PackingGroupCode", adr.get("packing_group", ""))
                _sub(dg, "ram:TunnelRestrictionCode", adr.get("tunnel_code", ""))
                if adr.get("quantity"):
                    _sub(dg, "ram:GrossMass",
                         str(adr["quantity"]), {"measureUnitCode": "KGM"})
        except (json.JSONDecodeError, TypeError):
            pass

    sigs = _sub(root, "Signatures")
    for party in ("sender", "carrier", "consignee"):
        _sub(sigs, "eFTI:Signature", attrib={"party": party, "status": "unsigned"})

    rough = tostring(root, encoding="unicode")
    try:
        dom = minidom.parseString(rough)
        return dom.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")
    except Exception:
        return rough
