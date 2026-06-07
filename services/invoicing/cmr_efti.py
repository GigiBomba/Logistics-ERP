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
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring, indent

logger = logging.getLogger(__name__)

NS_RSM = "urn:un:unece:uncefact:data:standard:CrossBorderRegulatoryNotification:100"
NS_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
NS_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"


def _sub(parent: Element, tag: str, text: Optional[str] = None,
         attrib: Optional[Dict[str, str]] = None) -> Element:
    el = SubElement(parent, tag, attrib or {})
    if text is not None:
        el.text = text
    return el


def _date_time(parent: Element, dt_str: str) -> None:
    _sub(parent, "udt:DateTime", dt_str)


def _safe_date(raw: str) -> str:
    """Normalize a date string — append ISO time if missing, return as-is if already ISO."""
    if not raw:
        return ""
    if raw and "T" in raw:
        return raw
    return raw + "T00:00:00Z"


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

    root = Element("rsm:CrossBorderRegulatoryNotification", {
        "xmlns:rsm": NS_RSM,
        "xmlns:ram": NS_RAM,
        "xmlns:udt": NS_UDT,
    })

    # ── HeaderExchangedDocument ──
    hed = _sub(root, "rsm:HeaderExchangedDocument")
    _sub(hed, "ram:ID", cmr_number)
    _sub(hed, "ram:TypeCode", "999")
    issue_dt = _sub(hed, "ram:IssueDateTime")
    _date_time(issue_dt, datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    # ── SpecifiedCrossBorderRegulatoryProcedure ──
    proc = _sub(root, "rsm:SpecifiedCrossBorderRegulatoryProcedure")
    _sub(proc, "ram:ID", "CMR")

    # ── Consignment ──
    cons = _sub(root, "ram:Consignment")
    _sub(cons, "ram:ID", cmr_number)

    # Consignor
    consignor = _sub(cons, "ram:ConsignorTradeParty")
    _sub(consignor, "ram:Name", company_config.get("company_name", ""))
    addr1 = _sub(consignor, "ram:PostalTradeAddress")
    _sub(addr1, "ram:LineOne", company_config.get("address", ""))
    _sub(addr1, "ram:CountryID", trip_data.get("loading_country", ""))
    vat = company_config.get("cui", "")
    if vat:
        tax1 = _sub(consignor, "ram:SpecifiedTaxRegistration")
        _sub(tax1, "ram:ID", vat, {"schemeID": "VA"})
    eori_val = company_config.get("eori_number", vat)
    if eori_val:
        tax2 = _sub(consignor, "ram:SpecifiedTaxRegistration")
        _sub(tax2, "ram:ID", eori_val, {"schemeID": "EORI"})

    # Consignee
    cd = client_data or {}
    consignee = _sub(cons, "ram:ConsigneeTradeParty")
    _sub(consignee, "ram:Name", cd.get("name", trip_data.get("client_name", "")))
    addr2 = _sub(consignee, "ram:PostalTradeAddress")
    _sub(addr2, "ram:LineOne", cd.get("address", trip_data.get("client_address", "")))
    _sub(addr2, "ram:CountryID", trip_data.get("delivery_country", ""))
    if cd.get("vat_number"):
        tax3 = _sub(consignee, "ram:SpecifiedTaxRegistration")
        _sub(tax3, "ram:ID", cd["vat_number"], {"schemeID": "VA"})
    if cd.get("eori_number"):
        tax4 = _sub(consignee, "ram:SpecifiedTaxRegistration")
        _sub(tax4, "ram:ID", cd["eori_number"], {"schemeID": "EORI"})

    # Carrier
    carrier = _sub(cons, "ram:CarrierTradeParty")
    _sub(carrier, "ram:Name", company_config.get("company_name", ""))
    if company_config.get("cui"):
        tax5 = _sub(carrier, "ram:SpecifiedTaxRegistration")
        _sub(tax5, "ram:ID", company_config["cui"], {"schemeID": "VA"})

    # Takeover Location
    takeover = _sub(cons, "ram:LogisticsLocationTakeOver")
    _sub(takeover, "ram:Name", trip_data.get("place_of_loading",
          trip_data.get("origin", trip_data.get("loading_address", ""))))
    _sub(takeover, "ram:CountryID", trip_data.get("loading_country", ""))
    if trip_data.get("place_of_loading_date"):
        dt = _sub(takeover, "ram:EffectiveDateTime")
        _date_time(dt, _safe_date(trip_data["place_of_loading_date"]))

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
    veh = truck_data or {}
    drv = driver_data or {}
    veh_id = veh.get("plate_number", trip_data.get("truck_plate",
                     trip_data.get("truck_number", "")))
    veh_move = _sub(cons, "ram:SpecifiedLogisticsTransportMovement")
    _sub(veh_move, "ram:ID", veh_id)
    _sub(veh_move, "ram:ModeCode", "3")
    veh_means = _sub(veh_move, "ram:UsedLogisticsTransportMeans")
    _sub(veh_means, "ram:ID", veh_id)
    trailer = veh.get("trailer_plate", trip_data.get("trailer_plate", ""))
    if trailer:
        tr = _sub(veh_move, "ram:AttachedLogisticsTransportEquipment")
        _sub(tr, "ram:ID", trailer)

    # Driver
    driver_name = drv.get("name", trip_data.get("driver_name", ""))
    if driver_name:
        driver = _sub(veh_move, "ram:SpecifiedTransportPerson")
        _sub(driver, "ram:Name", driver_name)
        lic = drv.get("license_number", trip_data.get("driver_license", ""))
        if lic:
            _sub(driver, "ram:ID", lic)

    # Successive Carriers
    succ = successive_carriers or trip_data.get("successive_carriers", [])
    for sc in succ:
        scp = _sub(cons, "ram:CarrierTradeParty")
        _sub(scp, "ram:Name", sc.get("carrier_name", ""))
        if sc.get("carrier_address"):
            sca = _sub(scp, "ram:PostalTradeAddress")
            _sub(sca, "ram:LineOne", sc["carrier_address"])
            if sc.get("carrier_country"):
                _sub(sca, "ram:CountryID", sc["carrier_country"])

    # Dangerous Goods
    adr_raw = trip_data.get("adr_info_json")
    if adr_raw:
        try:
            if isinstance(adr_raw, str):
                adr_items = json.loads(adr_raw)
            else:
                adr_items = adr_raw
            if isinstance(adr_items, list):
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
        except (json.JSONDecodeError, TypeError) as exc:
            logger.debug("ADR XML generation skipped: %s", exc)

    # Remarks / Instructions
    if trip_data.get("carrier_instructions") or trip_data.get("carrier_reservations"):
        remarks = _sub(root, "rsm:Remarks")
        if trip_data.get("carrier_instructions"):
            _sub(remarks, "ram:Content", trip_data["carrier_instructions"])
        if trip_data.get("carrier_reservations"):
            _sub(remarks, "ram:Content", trip_data["carrier_reservations"])

    # Signatures — one SpecifiedSignature per party per UN/CEFACT MMT-RDM
    for party in ("sender", "carrier", "consignee"):
        sigs = _sub(root, "rsm:SpecifiedSignature")
        sig = _sub(sigs, "ram:ExchangedDocument")
        _sub(sig, "ram:TypeCode", party)
        _sub(sig, "ram:StatusCode", "unsigned")

    # Pretty-print (Python 3.9+ indent)
    indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode")
