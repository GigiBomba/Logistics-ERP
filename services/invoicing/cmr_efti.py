"""eFTI-compliant eCMR XML generator for Operion ERP.

Produces structured XML conforming to UN/CEFACT MMT-RDM (Multi-Modal Transport
Reference Data Model) for electronic CMR under EU Regulation 2020/1056.

Schema: CrossBorderRegulatoryNotification (100)
Namespaces:
  rsm: urn:un:unece:uncefact:data:standard:CrossBorderRegulatoryNotification:100
  ram: urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100
  udt: urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

logger = logging.getLogger(__name__)

NS_RSM = "urn:un:unece:uncefact:data:standard:CrossBorderRegulatoryNotification:100"
NS_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
NS_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"


def _sub(parent: Element, tag: str, text: Optional[str] = None,
         attrib: Optional[Dict[str, str]] = None) -> Element:
    """Helper to create a namespaced sub-element."""
    el = SubElement(parent, tag, attrib or {})
    if text is not None:
        el.text = text
    return el


def _date_time(parent: Element, dt_str: str) -> None:
    """Add a udt:DateTime element."""
    _sub(parent, "udt:DateTime", dt_str)


def generate_efti_xml(
    cmr_number: str,
    trip_data: Dict[str, Any],
    company_config: Dict[str, Any],
    client_data: Optional[Dict[str, Any]] = None,
    truck_data: Optional[Dict[str, Any]] = None,
    driver_data: Optional[Dict[str, Any]] = None,
    successive_carriers: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate UN/CEFACT MMT-RDM compliant eCMR XML."""

    # ── Root ──
    root = Element("rsm:CrossBorderRegulatoryNotification", {
        "xmlns:rsm": NS_RSM,
        "xmlns:ram": NS_RAM,
        "xmlns:udt": NS_UDT,
    })

    # ── HeaderExchangedDocument ──
    hed = _sub(root, "rsm:HeaderExchangedDocument")
    _sub(hed, "ram:ID", cmr_number)
    _sub(hed, "ram:TypeCode", "999")  # 999 = CMR per UN/CEFACT
    issue_dt = _sub(hed, "ram:IssueDateTime")
    _date_time(issue_dt, datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))

    # ── SpecifiedCrossBorderRegulatoryProcedure ──
    proc = _sub(root, "rsm:SpecifiedCrossBorderRegulatoryProcedure")
    _sub(proc, "ram:ID", "CMR")

    # ── Consignment ──
    cons = _sub(root, "ram:Consignment")
    _sub(cons, "ram:ID", cmr_number)

    # Consignor Trade Party
    consignor = _sub(cons, "ram:ConsignorTradeParty")
    _sub(consignor, "ram:Name", company_config.get("company_name", ""))
    addr1 = _sub(consignor, "ram:PostalTradeAddress")
    _sub(addr1, "ram:LineOne", company_config.get("address", ""))
    _sub(addr1, "ram:CountryID", trip_data.get("loading_country", ""))
    if company_config.get("cui"):
        tax1 = _sub(consignor, "ram:SpecifiedTaxRegistration")
        _sub(tax1, "ram:ID", company_config["cui"], {"schemeID": "VA"})
    eori_val = company_config.get("eori_number", company_config.get("cui", ""))
    if eori_val:
        tax2 = _sub(consignor, "ram:SpecifiedTaxRegistration")
        _sub(tax2, "ram:ID", eori_val, {"schemeID": "EORI"})

    # Consignee Trade Party
    consignee = _sub(cons, "ram:ConsigneeTradeParty")
    client_name = trip_data.get("client_name", "")
    client_addr = trip_data.get("client_address", "")
    if client_data:
        client_name = client_data.get("name", client_name)
        client_addr = client_data.get("address", client_addr)
    _sub(consignee, "ram:Name", client_name)
    addr2 = _sub(consignee, "ram:PostalTradeAddress")
    _sub(addr2, "ram:LineOne", client_addr)
    _sub(addr2, "ram:CountryID", trip_data.get("delivery_country", ""))
    if client_data and client_data.get("vat_number"):
        tax3 = _sub(consignee, "ram:SpecifiedTaxRegistration")
        _sub(tax3, "ram:ID", client_data["vat_number"], {"schemeID": "VA"})

    # Carrier Trade Party
    carrier = _sub(cons, "ram:CarrierTradeParty")
    _sub(carrier, "ram:Name", company_config.get("company_name", ""))
    if company_config.get("cui"):
        tax4 = _sub(carrier, "ram:SpecifiedTaxRegistration")
        _sub(tax4, "ram:ID", company_config["cui"], {"schemeID": "VA"})

    # Takeover Location
    takeover = _sub(cons, "ram:LogisticsLocationTakeOver")
    _sub(takeover, "ram:Name", trip_data.get("place_of_loading",
          trip_data.get("origin", trip_data.get("loading_address", ""))))
    _sub(takeover, "ram:CountryID", trip_data.get("loading_country", ""))
    if trip_data.get("place_of_loading_date"):
        dt = _sub(takeover, "ram:EffectiveDateTime")
        _date_time(dt, trip_data["place_of_loading_date"] + "T00:00:00Z")

    # Delivery Location
    delivery = _sub(cons, "ram:LogisticsLocationDelivery")
    _sub(delivery, "ram:Name", trip_data.get("place_of_delivery",
          trip_data.get("destination", trip_data.get("unloading_address", ""))))
    _sub(delivery, "ram:CountryID", trip_data.get("delivery_country", ""))

    # Consignment Item
    item = _sub(cons, "ram:IncludedConsignmentItem")
    _sub(item, "ram:SequenceNumeric", "1")
    _sub(item, "ram:Description", trip_data.get("cargo_description", ""))
    if trip_data.get("gross_weight_kg"):
        _sub(item, "ram:GrossWeightMeasure", str(trip_data["gross_weight_kg"]),
             {"unitCode": "KGM"})
    if trip_data.get("volume_m3"):
        _sub(item, "ram:GrossVolumeMeasure", str(trip_data["volume_m3"]),
             {"unitCode": "MTQ"})
    if trip_data.get("package_count"):
        _sub(item, "ram:TotalPackageQuantity", str(trip_data["package_count"]))

    # Vehicle / Transport Means
    veh_move = _sub(cons, "ram:SpecifiedLogisticsTransportMovement")
    _sub(veh_move, "ram:ID", trip_data.get("truck_number",
          trip_data.get("truck_plate", "")))
    _sub(veh_move, "ram:ModeCode", "3")  # 3 = Road
    veh_means = _sub(veh_move, "ram:UsedLogisticsTransportMeans")
    _sub(veh_means, "ram:ID", trip_data.get("truck_plate",
          trip_data.get("truck_number", "")))
    if trip_data.get("trailer_plate"):
        trailer = _sub(veh_move, "ram:AttachedLogisticsTransportEquipment")
        _sub(trailer, "ram:ID", trip_data["trailer_plate"])

    # Driver
    if trip_data.get("driver_name"):
        driver = _sub(veh_move, "ram:SpecifiedTransportPerson")
        _sub(driver, "ram:Name", trip_data["driver_name"])
        if trip_data.get("driver_license"):
            _sub(driver, "ram:ID", trip_data["driver_license"])

    # Dangerous Goods
    if trip_data.get("adr_info_json"):
        try:
            adr_items = json.loads(trip_data["adr_info_json"])
            for adr in adr_items:
                dg = _sub(cons, "ram:IncludedDangerousGoods")
                if adr.get("un_no"):
                    _sub(dg, "ram:UNDGIdentifier", adr["un_no"])
                if adr.get("adr_class"):
                    _sub(dg, "ram:ClassificationCode", adr["adr_class"])
                if adr.get("packing_group"):
                    _sub(dg, "ram:PackingGroupCode", adr["packing_group"])
                if adr.get("tunnel_code"):
                    _sub(dg, "ram:TunnelRestrictionCode", adr["tunnel_code"])
                if adr.get("quantity"):
                    _sub(dg, "ram:GrossMassMeasure", str(adr["quantity"]),
                         {"unitCode": "KGM"})
        except (json.JSONDecodeError, TypeError):
            pass

    # Remarks / Instructions
    if trip_data.get("carrier_instructions") or trip_data.get("carrier_reservations"):
        remarks = _sub(root, "rsm:Remarks")
        if trip_data.get("carrier_instructions"):
            _sub(remarks, "ram:Content", trip_data["carrier_instructions"])
        if trip_data.get("carrier_reservations"):
            _sub(remarks, "ram:Content", trip_data["carrier_reservations"])

    # Signatures placeholder
    sigs = _sub(root, "rsm:SpecifiedSignature")
    for party in ("sender", "carrier", "consignee"):
        sig = _sub(sigs, "ram:ExchangedDocument")
        _sub(sig, "ram:TypeCode", party)
        _sub(sig, "ram:StatusCode", "unsigned")

    # Pretty-print
    rough = tostring(root, encoding="unicode")
    try:
        dom = minidom.parseString(rough)
        return dom.toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")
    except Exception:
        return rough
