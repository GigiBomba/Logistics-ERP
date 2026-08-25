#!/usr/bin/env python3
"""Boost HU and TR coverage by adding remaining translations."""
from __future__ import annotations

import json, os, re

TRANS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "translations")

def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

def flatten(d, prefix=""):
    """Flatten nested dict, preserving lists as-is."""
    items = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten(v, key))
        elif isinstance(v, list):
            items[key] = v  # Keep lists as-is
        else:
            items[key] = v
    return items

def set_nested(d, key_parts, value):
    cur = d
    for p in key_parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[key_parts[-1]] = value

def unflatten(flat):
    result = {}
    for key, value in sorted(flat.items()):
        parts = key.split(".")
        set_nested(result, parts, value)
    return result

# Load existing dicts to leverage existing translations
cs_phrases = load_json(os.path.join(TRANS_DIR, "_dict_cs_phrases.json"))
pt_phrases = load_json(os.path.join(TRANS_DIR, "_dict_pt_phrases.json"))

# Build remaining translation maps for HU and TR
# Format: {english_value: {hu: translation, tr: translation}}

MORE_TRANSLATIONS = {
    # Analytics subtitles (longer phrases)
    "Fleet performance analytics and KPIs": {"hu": "Flotta teljes\u00edtm\u00e9nyelemz\u00e9s \u00e9s KPI-k", "tr": "Filo performans analiti\u011fi ve KPI'lar"},
    "Revenue, profit, margin, and cash flow trends": {"hu": "Bev\u00e9tel, nyeres\u00e9g, \u00e1rr\u00e9s \u00e9s cash flow trendek", "tr": "Gelir, k\u00e2r, marj ve nakit ak\u0131\u015f\u0131 trendleri"},
    "Truck utilization, fuel efficiency, and maintenance alerts": {"hu": "Kamion kihaszn\u00e1lts\u00e1g, \u00fczemanyag-hat\u00e9konys\u00e1g \u00e9s karbantart\u00e1si riaszt\u00e1sok", "tr": "Kamyon kullan\u0131m\u0131, yak\u0131t verimlili\u011fi ve bak\u0131m uyar\u0131lar\u0131"},
    "Route profitability and country corridor analysis": {"hu": "\u00datvonal j\u00f6vedelmez\u0151s\u00e9g \u00e9s orsz\u00e1gfolyos\u00f3 elemz\u00e9s", "tr": "Rota k\u00e2rl\u0131l\u0131\u011f\u0131 ve \u00fclke koridoru analizi"},
    "Client revenue, payment behavior, and growth": {"hu": "\u00dcgyf\u00e9l bev\u00e9tel, fizet\u00e9si magatart\u00e1s \u00e9s n\u00f6veked\u00e9s", "tr": "M\u00fc\u015fteri geliri, \u00f6deme davran\u0131\u015f\u0131 ve b\u00fcy\u00fcme"},
    "Driver performance, efficiency, and compliance": {"hu": "Sof\u0151r teljes\u00edtm\u00e9ny, hat\u00e9konys\u00e1g \u00e9s megfelel\u0151s\u00e9g", "tr": "S\u00fcr\u00fcc\u00fc performans\u0131, verimlili\u011fi ve uyumu"},
    "Document volume, trends, and expiration tracking": {"hu": "Dokumentum mennyis\u00e9g, trendek \u00e9s lej\u00e1rat k\u00f6vet\u00e9s", "tr": "Belge hacmi, trendler ve son kullanma takibi"},
    "Truck Profitability": {"hu": "Kamion j\u00f6vedelmez\u0151s\u00e9g", "tr": "Kamyon K\u00e2rl\u0131l\u0131\u011f\u0131"},
    "Fuel Efficiency (L/100km)": {"hu": "\u00dczemanyag-hat\u00e9konys\u00e1g (L/100km)", "tr": "Yak\u0131t Verimlili\u011fi (L/100km)"},
    "Truck Utilization (Trips)": {"hu": "Kamion kihaszn\u00e1lts\u00e1g (utak)", "tr": "Kamyon Kullan\u0131m\u0131 (Seyahatler)"},
    "Revenue by Client": {"hu": "Bev\u00e9tel \u00fcgyf\u00e9l szerint", "tr": "M\u00fc\u015fteriye G\u00f6re Gelir"},
    "Profit by Client": {"hu": "Nyeres\u00e9g \u00fcgyf\u00e9l szerint", "tr": "M\u00fc\u015fteriye G\u00f6re K\u00e2r"},
    "Average Payment Delay (Days)": {"hu": "\u00c1tlagos fizet\u00e9si k\u00e9sedelem (nap)", "tr": "Ortalama \u00d6deme Gecikmesi (G\u00fcn)"},
    "Revenue Concentration": {"hu": "Bev\u00e9tel koncentr\u00e1ci\u00f3", "tr": "Gelir Yo\u011funla\u015fmas\u0131"},
    "Last quarter": {"hu": "Elm\u00falt negyed\u00e9v", "tr": "Ge\u00e7en \u00e7eyrek"},
    "New Clients per Month": {"hu": "\u00daj \u00fcgyfelek havonta", "tr": "Ayl\u0131k Yeni M\u00fc\u015fteriler"},
    "Trips Completed": {"hu": "Teljes\u00edtett utak", "tr": "Tamamlanan Seyahatler"},
    "Efficiency (Profit/km)": {"hu": "Hat\u00e9konys\u00e1g (nyeres\u00e9g/km)", "tr": "Verimlilik (K\u00e2r/km)"},
    "Tacho Violations (90 days)": {"hu": "Tachogr\u00e1f szab\u00e1lys\u00e9rt\u00e9sek (90 nap)", "tr": "Takograf \u0130hlalleri (90 g\u00fcn)"},
    "Most Profitable Routes": {"hu": "Legj\u00f6vedelmez\u0151bb \u00fatvonalak", "tr": "En K\u00e2rl\u0131 Rotalar"},
    "Profit per KM": {"hu": "Nyeres\u00e9g km-enk\u00e9nt", "tr": "KM Ba\u015f\u0131na K\u00e2r"},
    "Fuel Cost per KM": {"hu": "\u00dczemanyag k\u00f6lts\u00e9g km-enk\u00e9nt", "tr": "KM Ba\u015f\u0131na Yak\u0131t Maliyeti"},
    "Country Profit per KM": {"hu": "Orsz\u00e1g nyeres\u00e9g km-enk\u00e9nt", "tr": "\u00dclke Ba\u015f\u0131na KM K\u00e2r"},
    "Document Distribution": {"hu": "Dokumentum eloszl\u00e1s", "tr": "Belge Da\u011f\u0131l\u0131m\u0131"},
    "Monthly Uploads": {"hu": "Havi felt\u00f6lt\u00e9sek", "tr": "Ayl\u0131k Y\u00fcklemeler"},
    "CMR Generation Trend": {"hu": "CMR gener\u00e1l\u00e1si trend", "tr": "CMR Olu\u015fturma Trendi"},
    "Revenue by Country": {"hu": "Bev\u00e9tel orsz\u00e1g szerint", "tr": "\u00dclkeye G\u00f6re Gelir"},
    "Financial Trends": {"hu": "P\u00e9nz\u00fcgyi trendek", "tr": "Finansal Trendler"},
    "Financial Performance": {"hu": "P\u00e9nz\u00fcgyi teljes\u00edtm\u00e9ny", "tr": "Finansal Performans"},
    "Client & Geographic": {"hu": "\u00dcgyf\u00e9l \u00e9s f\u00f6ldrajzi", "tr": "M\u00fc\u015fteri ve Co\u011frafi"},
    "Volume & Cost": {"hu": "Mennyis\u00e9g \u00e9s k\u00f6lts\u00e9g", "tr": "Hacim ve Maliyet"},
    "Fleet Performance": {"hu": "Flotta teljes\u00edtm\u00e9ny", "tr": "Filo Performans\u0131"},
    "Fleet Composition": {"hu": "Flotta \u00f6sszet\u00e9tel", "tr": "Filo Kompozisyonu"},
    "Cost & Maintenance": {"hu": "K\u00f6lts\u00e9g \u00e9s karbantart\u00e1s", "tr": "Maliyet ve Bak\u0131m"},
    "Volume & Efficiency": {"hu": "Mennyis\u00e9g \u00e9s hat\u00e9konys\u00e1g", "tr": "Hacim ve Verimlilik"},
    "Compliance & Safety": {"hu": "Megfelel\u0151s\u00e9g \u00e9s biztons\u00e1g", "tr": "Uyum ve G\u00fcvenlik"},
    "Distribution & Insights": {"hu": "Eloszl\u00e1s \u00e9s betekint\u00e9sek", "tr": "Da\u011f\u0131l\u0131m ve \u0130\u00e7g\u00f6r\u00fcler"},
    "Trip Distance Distribution": {"hu": "\u00dat t\u00e1vols\u00e1g eloszl\u00e1s", "tr": "Seyahat Mesafesi Da\u011f\u0131l\u0131m\u0131"},
    "Trips by Month x Driver": {"hu": "Utak h\u00f3nap x sof\u0151r szerint", "tr": "Ay x S\u00fcr\u00fcc\u00fcye G\u00f6re Seyahatler"},
    "Profit Breakdown (Top Driver)": {"hu": "Nyeres\u00e9g bont\u00e1s (legjobb sof\u0151r)", "tr": "K\u00e2r D\u00f6k\u00fcm\u00fc (En \u0130yi S\u00fcr\u00fcc\u00fc)"},
    "Driving vs Rest Hours": {"hu": "Vezet\u00e9s vs pihen\u0151 \u00f3r\u00e1k", "tr": "S\u00fcr\u00fc\u015f vs Dinlenme Saatleri"},
    "Driver Utilization Score": {"hu": "Sof\u0151r kihaszn\u00e1lts\u00e1gi pontsz\u00e1m", "tr": "S\u00fcr\u00fcc\u00fc Kullan\u0131m Puan\u0131"},
    "Avg Profit per Trip": {"hu": "\u00c1tl. nyeres\u00e9g \u00fatonk\u00e9nt", "tr": "Seyahat Ba\u015f\u0131na Ort. K\u00e2r"},
    "Total costs": {"hu": "Teljes k\u00f6lts\u00e9gek", "tr": "Toplam maliyetler"},
    "Top Route": {"hu": "Legjobb \u00fatvonal", "tr": "En \u0130yi Rota"},
    "Avg Profit/km": {"hu": "\u00c1tl. nyeres\u00e9g/km", "tr": "Ort. K\u00e2r/km"},
    "Total Routes": {"hu": "\u00d6ssz. \u00fatvonal", "tr": "Toplam Rota"},
    "Top Country": {"hu": "Legjobb orsz\u00e1g", "tr": "En \u0130yi \u00dclke"},
    "Route Performance": {"hu": "\u00datvonal teljes\u00edtm\u00e9ny", "tr": "Rota Performans\u0131"},
    "Geographic Analysis": {"hu": "F\u00f6ldrajzi elemz\u00e9s", "tr": "Co\u011frafi Analiz"},
    "Correlation & Distribution": {"hu": "Korrel\u00e1ci\u00f3 \u00e9s eloszl\u00e1s", "tr": "Korelasyon ve Da\u011f\u0131l\u0131m"},
    "Volume & Trends": {"hu": "Mennyis\u00e9g \u00e9s trendek", "tr": "Hacim ve Trendler"},
    "Top Countries by Volume": {"hu": "Legjobb orsz\u00e1gok mennyis\u00e9g szerint", "tr": "Hacme G\u00f6re En \u0130yi \u00dclkeler"},
    "Top Countries by Profit": {"hu": "Legjobb orsz\u00e1gok nyeres\u00e9g szerint", "tr": "K\u00e2ra G\u00f6re En \u0130yi \u00dclkeler"},
    "Cost Breakdown": {"hu": "K\u00f6lts\u00e9g bont\u00e1s", "tr": "Maliyet D\u00f6k\u00fcm\u00fc"},
    "Distance Distribution": {"hu": "T\u00e1vols\u00e1g eloszl\u00e1s", "tr": "Mesafe Da\u011f\u0131l\u0131m\u0131"},
    "Route Length Trend": {"hu": "\u00datvonal hossz trend", "tr": "Rota Uzunlu\u011fu Trendi"},
    "Net Profit Trend": {"hu": "Nett\u00f3 nyeres\u00e9g trend", "tr": "Net K\u00e2r Trendi"},
    "Monthly Trip Volume": {"hu": "Havi \u00fat mennyis\u00e9g", "tr": "Ayl\u0131k Seyahat Hacmi"},
    "Idle": {"hu": "T\u00e9tlen", "tr": "Bo\u015fta"},
    "Client Performance": {"hu": "\u00dcgyf\u00e9l teljes\u00edtm\u00e9ny", "tr": "M\u00fc\u015fteri Performans\u0131"},
    "Client Composition": {"hu": "\u00dcgyf\u00e9l \u00f6sszet\u00e9tel", "tr": "M\u00fc\u015fteri Kompozisyonu"},
    "Client Trends": {"hu": "\u00dcgyf\u00e9l trendek", "tr": "M\u00fc\u015fteri Trendleri"},
    "Client Insights": {"hu": "\u00dcgyf\u00e9l betekint\u00e9sek", "tr": "M\u00fc\u015fteri \u0130\u00e7g\u00f6r\u00fcleri"},
    "Document Overview": {"hu": "Dokumentum \u00e1ttekint\u00e9s", "tr": "Belge Genel Bak\u0131\u015f"},
    "Document Breakdown": {"hu": "Dokumentum bont\u00e1s", "tr": "Belge D\u00f6k\u00fcm\u00fc"},
    "Expiry & Aging": {"hu": "Lej\u00e1rat \u00e9s \u00f6reged\u00e9s", "tr": "Sona Erme ve Ya\u015fland\u0131rma"},
    "Growth & Trends": {"hu": "N\u00f6veked\u00e9s \u00e9s trendek", "tr": "B\u00fcy\u00fcme ve Trendler"},
    "Document Type Breakdown": {"hu": "Dokumentum t\u00edpus bont\u00e1s", "tr": "Belge T\u00fcr\u00fc D\u00f6k\u00fcm\u00fc"},
    "Category Distribution": {"hu": "Kateg\u00f3ria eloszl\u00e1s", "tr": "Kategori Da\u011f\u0131l\u0131m\u0131"},
    "Upload by Quarter": {"hu": "Felt\u00f6lt\u00e9s negyed\u00e9venk\u00e9nt", "tr": "\u00c7eyre\u011fe G\u00f6re Y\u00fckleme"},
    "Expiry Timeline": {"hu": "Lej\u00e1rati id\u0151vonal", "tr": "Sona Erme Zaman \u00c7izelgesi"},
    "Document Aging": {"hu": "Dokumentum \u00f6reged\u00e9s", "tr": "Belge Ya\u015fland\u0131rma"},
    "Expiring by Type": {"hu": "Lej\u00e1r\u00f3 t\u00edpus szerint", "tr": "T\u00fcr\u00fcne G\u00f6re Sona Erenler"},
    "Document Growth": {"hu": "Dokumentum n\u00f6veked\u00e9s", "tr": "Belge B\u00fcy\u00fcmesi"},
    "Volume vs Revenue": {"hu": "Mennyis\u00e9g vs bev\u00e9tel", "tr": "Hacim vs Gelir"},
    "Total Documents Trend": {"hu": "\u00d6ssz. dokumentum trend", "tr": "Toplam Belge Trendi"},
    "Revenue per Client Trend": {"hu": "Bev\u00e9tel \u00fcgyfelenk\u00e9nti trend", "tr": "M\u00fc\u015fteri Ba\u015f\u0131na Gelir Trendi"},
    "Trip Count Trend": {"hu": "\u00dat sz\u00e1ml\u00e1l\u00f3 trend", "tr": "Seyahat Say\u0131s\u0131 Trendi"},
    "Profit Margin per Client": {"hu": "Nyeres\u00e9g \u00e1rr\u00e9s \u00fcgyfelenk\u00e9nt", "tr": "M\u00fc\u015fteri Ba\u015f\u0131na K\u00e2r Marj\u0131"},
    "Revenue vs Profit": {"hu": "Bev\u00e9tel vs nyeres\u00e9g", "tr": "Gelir vs K\u00e2r"},
    "Active Clients Trend": {"hu": "Akt\u00edv \u00fcgyfelek trend", "tr": "Aktif M\u00fc\u015fteri Trendi"},
    "Total Clients": {"hu": "\u00d6ssz. \u00fcgyf\u00e9l", "tr": "Toplam M\u00fc\u015fteri"},
    "Avg Payment Delay": {"hu": "\u00c1tl. fizet\u00e9si k\u00e9s\u00e9s", "tr": "Ort. \u00d6deme Gecikmesi"},
    "Concentration": {"hu": "Koncentr\u00e1ci\u00f3", "tr": "Yo\u011funla\u015fma"},
    "Safety Score": {"hu": "Biztons\u00e1gi pontsz\u00e1m", "tr": "G\u00fcvenlik Puan\u0131"},
    "Active vs Inactive": {"hu": "Akt\u00edv vs inakt\u00edv", "tr": "Aktif vs Pasif"},
    "Client Retention": {"hu": "\u00dcgyf\u00e9l megtart\u00e1s", "tr": "M\u00fc\u015fteri Tutma"},
    "Cost Per Truck": {"hu": "K\u00f6lts\u00e9g kamiononk\u00e9nt", "tr": "Kamyon Ba\u015f\u0131na Maliyet"},
    "Country Corridors": {"hu": "Orsz\u00e1g folyos\u00f3k", "tr": "\u00dclke Koridorlar\u0131"},
    "Driver Distance": {"hu": "Sof\u0151r t\u00e1vols\u00e1g", "tr": "S\u00fcr\u00fcc\u00fc Mesafesi"},
    "Driver Driving Hours": {"hu": "Sof\u0151r vezet\u00e9si \u00f3r\u00e1k", "tr": "S\u00fcr\u00fcc\u00fc S\u00fcr\u00fc\u015f Saatleri"},
    "Driver Ranking": {"hu": "Sof\u0151r rangsor", "tr": "S\u00fcr\u00fcc\u00fc S\u0131ralamas\u0131"},
    "Driver Rest Hours": {"hu": "Sof\u0151r pihen\u0151 \u00f3r\u00e1k", "tr": "S\u00fcr\u00fcc\u00fc Dinlenme Saatleri"},
    "Efficiency Trend": {"hu": "Hat\u00e9konys\u00e1g trend", "tr": "Verimlilik Trendi"},
    "Extra Costs": {"hu": "Extra k\u00f6lts\u00e9gek", "tr": "Ekstra Maliyetler"},
    "Fuel Cost Trend": {"hu": "\u00dczemanyag k\u00f6lts\u00e9g trend", "tr": "Yak\u0131t Maliyeti Trendi"},
    "Fuel Efficiency Trend": {"hu": "\u00dczemanyag hat\u00e9konys\u00e1g trend", "tr": "Yak\u0131t Verimlili\u011fi Trendi"},
    "Idle Vs Active": {"hu": "T\u00e9tlen vs akt\u00edv", "tr": "Bo\u015fta vs Aktif"},
    "Invoiced Vs Paid": {"hu": "Sz\u00e1ml\u00e1zva vs fizetve", "tr": "Faturaland\u0131 vs \u00d6dendi"},
    "Maintenance Cost": {"hu": "Karbantart\u00e1si k\u00f6lts\u00e9g", "tr": "Bak\u0131m Maliyeti"},
    "Mileage Ranking": {"hu": "Fut\u00e1steljes\u00edtm\u00e9ny rangsor", "tr": "Kilometre S\u0131ralamas\u0131"},
    "Quarterly Revenue": {"hu": "Negyed\u00e9ves bev\u00e9tel", "tr": "\u00c7eyreklik Gelir"},
    "Profit Vs Distance": {"hu": "Nyeres\u00e9g vs t\u00e1vols\u00e1g", "tr": "K\u00e2r vs Mesafe"},
    "Truck Age Distribution": {"hu": "Kamion kor eloszl\u00e1s", "tr": "Kamyon Ya\u015f Da\u011f\u0131l\u0131m\u0131"},
    "31-60 days": {"hu": "31-60 nap", "tr": "31-60 g\u00fcn"},
    "61-90 days": {"hu": "61-90 nap", "tr": "61-90 g\u00fcn"},
    "Current (0-30d)": {"hu": "Aktu\u00e1lis (0-30n)", "tr": "G\u00fcncel (0-30g)"},
    "90+ days": {"hu": "90+ nap", "tr": "90+ g\u00fcn"},
    "All Countries": {"hu": "Minden orsz\u00e1g", "tr": "T\u00fcm \u00dclkeler"},
    "Actual Uploads": {"hu": "T\u00e9nyleges felt\u00f6lt\u00e9sek", "tr": "Ger\u00e7ek Y\u00fcklemeler"},
    "Expected (Trips)": {"hu": "V\u00e1rhat\u00f3 (utak)", "tr": "Beklenen (Seyahatler)"},
    "No documents expiring within 30 days": {"hu": "Nincs 30 napon bel\u00fcl lej\u00e1r\u00f3 dokumentum", "tr": "30 g\u00fcn i\u00e7inde sona eren belge yok"},
    "See all ({count})": {"hu": "\u00d6sszes megtekint\u00e9se ({count})", "tr": "T\u00fcm\u00fcn\u00fc g\u00f6r ({count})"},
    "Document Uploads vs Expected": {"hu": "Dokumentum felt\u00f6lt\u00e9sek vs v\u00e1rhat\u00f3", "tr": "Belge Y\u00fcklemeleri vs Beklenen"},
    "Outstanding Invoices by Age": {"hu": "Kintlev\u0151 sz\u00e1ml\u00e1k kor szerint", "tr": "Ya\u015fa G\u00f6re Bekleyen Faturalar"},
    "Active Drivers": {"hu": "Akt\u00edv sof\u0151r\u00f6k", "tr": "Aktif S\u00fcr\u00fcc\u00fcler"},
    "Avg Profit/Driver": {"hu": "\u00c1tl. nyeres\u00e9g/sof\u0151r", "tr": "Ort. K\u00e2r/S\u00fcr\u00fcc\u00fc"},
    "Avg Profit/Route": {"hu": "\u00c1tl. nyeres\u00e9g/\u00fatvonal", "tr": "Ort. K\u00e2r/Rota"},
    "Avg Trips/Driver": {"hu": "\u00c1tl. utak/sof\u0151r", "tr": "Ort. Seyahat/S\u00fcr\u00fcc\u00fc"},
    "Avg Cost/km": {"hu": "\u00c1tl. k\u00f6lts\u00e9g/km", "tr": "Ort. Maliyet/km"},
    "Avg collection period": {"hu": "\u00c1tl. beszed\u00e9si id\u0151", "tr": "Ort. tahsilat s\u00fcresi"},
    "DSO (Days)": {"hu": "DSO (napok)", "tr": "DSO (G\u00fcnler)"},
    "Most Frequent": {"hu": "Leggyakoribb", "tr": "En S\u0131k"},
    "New Clients": {"hu": "\u00daj \u00fcgyfelek", "tr": "Yeni M\u00fc\u015fteriler"},
    "Unique Routes": {"hu": "Egyedi \u00fatvonalak", "tr": "Benzersiz Rotalar"},
    "No assigned driver data for this period.": {"hu": "Nincs hozz\u00e1rendelt sof\u0151r adat erre az id\u0151szakra.", "tr": "Bu d\u00f6nem i\u00e7in atanm\u0131\u015f s\u00fcr\u00fcc\u00fc verisi yok."},
    "Outstanding": {"hu": "Kintlev\u0151", "tr": "Bekleyen"},
    "Target 30d": {"hu": "C\u00e9l 30n", "tr": "Hedef 30g"},
    "Refresh data": {"hu": "Adatok friss\u00edt\u00e9se", "tr": "Verileri yenile"},
    "Revenue vs Profit Trend": {"hu": "Bev\u00e9tel vs nyeres\u00e9g trend", "tr": "Gelir vs K\u00e2r Trendi"},
    "Route Frequency": {"hu": "\u00datvonal gyakoris\u00e1g", "tr": "Rota S\u0131kl\u0131\u011f\u0131"},
    "Driver Activity Timeline": {"hu": "Sof\u0151r aktivit\u00e1s id\u0151vonal", "tr": "S\u00fcr\u00fcc\u00fc Aktivite Zaman \u00c7izelgesi"},
    "Invoice Aging": {"hu": "Sz\u00e1mla \u00f6reged\u00e9s", "tr": "Fatura Ya\u015fland\u0131rma"},
    "Payment Behavior": {"hu": "Fizet\u00e9si magatart\u00e1s", "tr": "\u00d6deme Davran\u0131\u015f\u0131"},
    "Revenue & Profit Trend": {"hu": "Bev\u00e9tel \u00e9s nyeres\u00e9g trend", "tr": "Gelir ve K\u00e2r Trendi"},
    "No revenue data yet": {"hu": "M\u00e9g nincs bev\u00e9tel adat", "tr": "Hen\u00fcz gelir verisi yok"},
    "Expires": {"hu": "Lej\u00e1r", "tr": "Sona erer"},
    # Invoice section
    "Button Email": {"hu": "Email gomb", "tr": "E-posta D\u00fc\u011fmesi"},
    "Default Client": {"hu": "Alap\u00e9rtelmezett \u00fcgyf\u00e9l", "tr": "Varsay\u0131lan M\u00fc\u015fteri"},
    "Email Body": {"hu": "Email t\u00f6rzs", "tr": "E-posta G\u00f6vdesi"},
    "Email Failed": {"hu": "Email sikertelen", "tr": "E-posta Ba\u015far\u0131s\u0131z"},
    "Email Subject": {"hu": "Email t\u00e1rgya", "tr": "E-posta Konusu"},
    "Email Success": {"hu": "Email sikeres", "tr": "E-posta Ba\u015far\u0131l\u0131"},
    "Smtp Not Configured": {"hu": "SMTP nincs konfigur\u00e1lva", "tr": "SMTP Yap\u0131land\u0131r\u0131lmam\u0131\u015f"},
    # Settings
    "EMAIL & SMTP": {"hu": "EMAIL \u00c9S SMTP", "tr": "E-POSTA VE SMTP"},
    "MAINTENANCE THRESHOLDS": {"hu": "KARBANTART\u00c1SI K\u00dcSZ\u00d6B\u00d6K", "tr": "BAKIM E\u015e\u0130KLER\u0130"},
    "Application Settings": {"hu": "Alkalmaz\u00e1s be\u00e1ll\u00edt\u00e1sok", "tr": "Uygulama Ayarlar\u0131"},
    "SMTP Server:": {"hu": "SMTP szerver:", "tr": "SMTP Sunucu:"},
    "SMTP Port:": {"hu": "SMTP port:", "tr": "SMTP Port:"},
    "SMTP User:": {"hu": "SMTP felhaszn\u00e1l\u00f3:", "tr": "SMTP Kullan\u0131c\u0131:"},
    "SMTP Password:": {"hu": "SMTP jelsz\u00f3:", "tr": "SMTP \u015eifre:"},
    "Alert Email Recipients:": {"hu": "Riaszt\u00e1si email c\u00edmzettek:", "tr": "Uyar\u0131 E-posta Al\u0131c\u0131lar\u0131:"},
    "Alert Days Ahead:": {"hu": "Figyelmeztet\u00e9s napokkal el\u0151re:", "tr": "Uyar\u0131 G\u00fcn \u00d6ncesi:"},
    "Tacho Warning Days:": {"hu": "Tachogr\u00e1f figyelmeztet\u00e9si napok:", "tr": "Takograf Uyar\u0131 G\u00fcnleri:"},
    "Tacho Critical Days:": {"hu": "Tachogr\u00e1f kritikus napok:", "tr": "Takograf Kritik G\u00fcnler:"},
    "Test Connection": {"hu": "Kapcsolat tesztel\u00e9se", "tr": "Ba\u011flant\u0131y\u0131 Test Et"},
    "Email Logs": {"hu": "Email napl\u00f3k", "tr": "E-posta G\u00fcnl\u00fckleri"},
    "Connection successful": {"hu": "Kapcsolat sikeres", "tr": "Ba\u011flant\u0131 ba\u015far\u0131l\u0131"},
    "Test failed: {}": {"hu": "Teszt sikertelen: {}", "tr": "Test ba\u015far\u0131s\u0131z: {}"},
    "BRANDING": {"hu": "BRANDING", "tr": "MARKALA\u015eTIRMA"},
    "Company Logo:": {"hu": "C\u00e9g log\u00f3:", "tr": "\u015eirket Logosu:"},
    "Signature Image:": {"hu": "Al\u00e1\u00edr\u00e1s k\u00e9p:", "tr": "\u0130mza Resmi:"},
    "Stamp Image:": {"hu": "B\u00e9lyegz\u0151 k\u00e9p:", "tr": "Damga Resmi:"},
    "Body template:": {"hu": "Test sablon:", "tr": "G\u00f6vde \u015fablonu:"},
    "PaddleOCR advanced settings:": {"hu": "PaddleOCR halad\u00f3 be\u00e1ll\u00edt\u00e1sok:", "tr": "PaddleOCR geli\u015fmi\u015f ayarlar:"},
    "Cloud OCR credentials:": {"hu": "Cloud OCR hiteles\u00edt\u0151 adatok:", "tr": "Cloud OCR kimlik bilgileri:"},
    "Set at least one provider": {"hu": "Legal\u00e1bb egy szolg\u00e1ltat\u00f3t adjon meg", "tr": "En az bir sa\u011flay\u0131c\u0131 belirleyin"},
    " seconds": {"hu": " m\u00e1sodperc", "tr": " saniye"},
    # Dispatch board section
    "LIVE": {"hu": "\u00c9L\u0150", "tr": "CANLI"},
    "Board": {"hu": "T\u00e1bla", "tr": "Pano"},
    "Resources": {"hu": "Forr\u00e1sok", "tr": "Kaynaklar"},
    "Alerts & Ops": {"hu": "Riaszt\u00e1sok \u00e9s m\u0171veletek", "tr": "Uyar\u0131lar ve Operasyonlar"},
    "Timeline": {"hu": "Id\u0151vonal", "tr": "Zaman \u00c7izelgesi"},
    "Clear": {"hu": "T\u00f6rl\u00e9s", "tr": "Temizle"},
    "Filter by status": {"hu": "Sz\u0171r\u00e9s \u00e1llapot szerint", "tr": "Duruma g\u00f6re filtrele"},
    "No matching trips": {"hu": "Nincs megfelel\u0151 \u00fat", "tr": "E\u015fle\u015fen seyahat yok"},
    "Driver Availability": {"hu": "Sof\u0151r el\u00e9rhet\u0151s\u00e9g", "tr": "S\u00fcr\u00fcc\u00fc M\u00fcsaitli\u011fi"},
    "Truck Availability": {"hu": "Kamion el\u00e9rhet\u0151s\u00e9g", "tr": "Kamyon M\u00fcsaitli\u011fi"},
    "Available": {"hu": "El\u00e9rhet\u0151", "tr": "M\u00fcsait"},
    "Returning": {"hu": "Visszat\u00e9r\u0151", "tr": "D\u00f6n\u00fcyor"},
    "On Trip": {"hu": "\u00daton", "tr": "Seyahatte"},
    "Blocked": {"hu": "Blokkolt", "tr": "Engellendi"},
    "No active drivers": {"hu": "Nincs akt\u00edv sof\u0151r", "tr": "Aktif s\u00fcr\u00fcc\u00fc yok"},
    "No active trucks": {"hu": "Nincs akt\u00edv kamion", "tr": "Aktif kamyon yok"},
    "License Expired": {"hu": "Jogos\u00edtv\u00e1ny lej\u00e1rt", "tr": "Ehliyet Sona Erdi"},
    "Medical Expired": {"hu": "Orvosi lej\u00e1rt", "tr": "Sa\u011fl\u0131k Raporu Sona Erdi"},
    "Hours Exceeded": {"hu": "\u00d3r\u00e1k t\u00fall\u00e9pve", "tr": "Saatler A\u015f\u0131ld\u0131"},
    "Maint. Due": {"hu": "Karbantart\u00e1s esed\u00e9kes", "tr": "Bak\u0131m Zaman\u0131 Geldi"},
    "Insurance Expired": {"hu": "Biztos\u00edt\u00e1s lej\u00e1rt", "tr": "Sigorta Sona Erdi"},
    "Inspection Expired": {"hu": "Ellen\u0151rz\u00e9s lej\u00e1rt", "tr": "Muayene Sona Erdi"},
    "In Service": {"hu": "Szolg\u00e1latban", "tr": "Serviste"},
    "Trip": {"hu": "\u00dat", "tr": "Seyahat"},
    "Next free": {"hu": "K\u00f6vetkez\u0151 szabad", "tr": "Sonraki bo\u015f"},
    "Operational Alerts": {"hu": "M\u0171veleti riaszt\u00e1sok", "tr": "Operasyonel Uyar\u0131lar"},
    "No active alerts": {"hu": "Nincs akt\u00edv riaszt\u00e1s", "tr": "Aktif uyar\u0131 yok"},
    "All alerts have been resolved": {"hu": "Minden riaszt\u00e1s megoldva", "tr": "T\u00fcm uyar\u0131lar \u00e7\u00f6z\u00fcld\u00fc"},
    "Unassigned Trips": {"hu": "Hozz\u00e1 nem rendelt utak", "tr": "Atanmam\u0131\u015f Seyahatler"},
    "All trips assigned": {"hu": "Minden \u00fat hozz\u00e1rendelve", "tr": "T\u00fcm seyahatler atand\u0131"},
    "All trips are fully assigned": {"hu": "Minden \u00fat teljesen hozz\u00e1rendelve", "tr": "T\u00fcm seyahatler tamamen atand\u0131"},
    "No Truck": {"hu": "Nincs kamion", "tr": "Kamyon yok"},
    "No Driver": {"hu": "Nincs sof\u0151r", "tr": "S\u00fcr\u00fcc\u00fc yok"},
    "No Truck or Driver": {"hu": "Nincs kamion vagy sof\u0151r", "tr": "Kamyon veya s\u00fcr\u00fcc\u00fc yok"},
    "Quick Assign": {"hu": "Gyors hozz\u00e1rendel\u00e9s", "tr": "H\u0131zl\u0131 Ata"},
    "Assignment Summary": {"hu": "Hozz\u00e1rendel\u00e9s \u00f6sszefoglal\u00f3", "tr": "Atama \u00d6zeti"},
    "Total Active": {"hu": "\u00d6sszes akt\u00edv", "tr": "Toplam Aktif"},
    "Fully Assigned": {"hu": "Teljesen hozz\u00e1rendelve", "tr": "Tamamen Atand\u0131"},
    "Partial": {"hu": "R\u00e9szleges", "tr": "K\u0131smi"},
    "Resolve All": {"hu": "\u00d6sszes megold\u00e1sa", "tr": "T\u00fcm\u00fcn\u00fc \u00c7\u00f6z"},
    "Trip Details": {"hu": "\u00dat r\u00e9szletei", "tr": "Seyahat Detaylar\u0131"},
    "Edit Trip": {"hu": "\u00dat szerkeszt\u00e9se", "tr": "Seyahati D\u00fczenle"},
    "Trip ID": {"hu": "\u00dat azonos\u00edt\u00f3", "tr": "Seyahat ID"},
    "Departure": {"hu": "Indul\u00e1s", "tr": "Kalk\u0131\u015f"},
    "Price": {"hu": "\u00c1r", "tr": "Fiyat"},
    "Currency": {"hu": "P\u00e9nznem", "tr": "Para Birimi"},
    "Notes": {"hu": "Megjegyz\u00e9sek", "tr": "Notlar"},
    "No alerts for this trip": {"hu": "Nincs riaszt\u00e1s ehhez az \u00fathoz", "tr": "Bu seyahat i\u00e7in uyar\u0131 yok"},
    "Resource Conflict": {"hu": "Er\u0151forr\u00e1s \u00fctk\u00f6z\u00e9s", "tr": "Kaynak \u00c7ak\u0131\u015fmas\u0131"},
    "Drivers Free": {"hu": "Szabad sof\u0151r\u00f6k", "tr": "Bo\u015ftaki S\u00fcr\u00fcc\u00fcler"},
    "Trucks Free": {"hu": "Szabad kamionok", "tr": "Bo\u015ftaki Kamyonlar"},
    "Schedule Timeline": {"hu": "\u00dctemez\u00e9s id\u0151vonal", "tr": "Program Zaman \u00c7izelgesi"},
    "Plan a Trip": {"hu": "\u00dat tervez\u00e9se", "tr": "Seyahat Planla"},
    "NOW": {"hu": "MOST", "tr": "\u015e\u0130MD\u0130"},
    "Assign Truck + Driver": {"hu": "Kamion + sof\u0151r hozz\u00e1rendel\u00e9se", "tr": "Kamyon + S\u00fcr\u00fcc\u00fc Ata"},
    "Cancel Trip": {"hu": "\u00dat t\u00f6rl\u00e9se", "tr": "Seyahati \u0130ptal Et"},
    "Today's Brief": {"hu": "Mai \u00f6sszefoglal\u00f3", "tr": "Bug\u00fcnk\u00fc \u00d6zet"},
    "Departing Today": {"hu": "Ma indul\u00f3", "tr": "Bug\u00fcn Ayr\u0131lanlar"},
    "Arriving Today": {"hu": "Ma \u00e9rkez\u0151", "tr": "Bug\u00fcn Gelenler"},
    "Needs Attention": {"hu": "Figyelmet ig\u00e9nyel", "tr": "\u0130lgi Gerektiriyor"},
    "Assign Truck": {"hu": "Kamion hozz\u00e1rendel\u00e9se", "tr": "Kamyon Ata"},
    "Assign Driver": {"hu": "Sof\u0151r hozz\u00e1rendel\u00e9se", "tr": "S\u00fcr\u00fcc\u00fc Ata"},
    "Select Truck": {"hu": "Kamion kiv\u00e1laszt\u00e1sa", "tr": "Kamyon Se\u00e7"},
    "Select Driver": {"hu": "Sof\u0151r kiv\u00e1laszt\u00e1sa", "tr": "S\u00fcr\u00fcc\u00fc Se\u00e7"},
    "Assign Both": {"hu": "Mindkett\u0151 hozz\u00e1rendel\u00e9se", "tr": "Her \u0130kisini de Ata"},
    "Nothing to undo": {"hu": "Nincs mit visszavonni", "tr": "Geri al\u0131nacak bir \u015fey yok"},
    "Nothing to redo": {"hu": "Nincs mit megism\u00e9telni", "tr": "Tekrarlanacak bir \u015fey yok"},
    "No trips found": {"hu": "Nem tal\u00e1lhat\u00f3 \u00fat", "tr": "Seyahat bulunamad\u0131"},
    # Receipt section
    "Receipt Photo": {"hu": "Nyugta fot\u00f3", "tr": "Makbuz Foto\u011fraf\u0131"},
    "Fuel Receipt": {"hu": "\u00dczemanyag nyugta", "tr": "Yak\u0131t Makbuzu"},
    "Amount in Words": {"hu": "\u00d6sszeg bet\u0171kkel", "tr": "Tutari Yaziyla"},
    "Employee Name": {"hu": "Alkalmazott neve", "tr": "\u00c7al\u0131\u015fan Ad\u0131"},
    "Expense Category": {"hu": "K\u00f6lts\u00e9g kateg\u00f3ria", "tr": "Gider Kategorisi"},
    "Pickup Location": {"hu": "Rakod\u00e1s helye", "tr": "Y\u00fckleme Yeri"},
    "Delivery Location": {"hu": "Kisz\u00e1ll\u00edt\u00e1s helye", "tr": "Teslimat Yeri"},
    "Reference No.": {"hu": "Hivatkoz\u00e1si sz\u00e1m", "tr": "Referans No."},
    "Transaction ID": {"hu": "Tranzakci\u00f3 azonos\u00edt\u00f3", "tr": "\u0130\u015flem ID"},
    "Payment Method": {"hu": "Fizet\u00e9si m\u00f3d", "tr": "\u00d6deme Y\u00f6ntemi"},
    "Received From": {"hu": "Kapva innen", "tr": "Kimden Al\u0131nd\u0131"},
    "Received By": {"hu": "\u00c1tvev\u0151", "tr": "Kimin Taraf\u0131ndan Al\u0131nd\u0131"},
    "VAT Rate (%)": {"hu": "\u00c1FA kulcs (%)", "tr": "KDV Oran\u0131 (%)"},
    "VAT Amount": {"hu": "\u00c1FA \u00f6sszeg", "tr": "KDV Tutar\u0131"},
    "Company Logo": {"hu": "C\u00e9g log\u00f3", "tr": "\u015eirket Logosu"},
    "Validation Error": {"hu": "\u00c9rv\u00e9nyes\u00edt\u00e9si hiba", "tr": "Do\u011frulama Hatas\u0131"},
    "Receipt Generated": {"hu": "Nyugta gener\u00e1lva", "tr": "Makbuz Olu\u015fturuldu"},
    "Receipt Duplicated": {"hu": "Nyugta m\u00e1solva", "tr": "Makbuz Kopyaland\u0131"},
    "Attach Files": {"hu": "F\u00e1jlok csatol\u00e1sa", "tr": "Dosyalar\u0131 Ekle"},
    "No file selected": {"hu": "Nincs f\u00e1jl kiv\u00e1lasztva", "tr": "Dosya se\u00e7ilmedi"},
    "Max file size": {"hu": "Max f\u00e1jl m\u00e9ret", "tr": "Maks. dosya boyutu"},
    "Upload & Run OCR": {"hu": "Felt\u00f6lt\u00e9s \u00e9s OCR futtat\u00e1sa", "tr": "Y\u00fckle ve OCR \u00c7al\u0131\u015ft\u0131r"},
    "File too large": {"hu": "T\u00fal nagy f\u00e1jl", "tr": "Dosya \u00e7ok b\u00fcy\u00fck"},
    "Upload Error": {"hu": "Felt\u00f6lt\u00e9si hiba", "tr": "Y\u00fckleme Hatas\u0131"},
    "Extracted Fields": {"hu": "Kinyert mez\u0151k", "tr": "Ay\u0131klanan Alanlar"},
    "Select Document": {"hu": "Dokumentum kiv\u00e1laszt\u00e1sa", "tr": "Belge Se\u00e7"},
    "From Date": {"hu": "D\u00e1tumt\u00f3l", "tr": "Ba\u015flang\u0131\u00e7 Tarihi"},
    "To Date": {"hu": "D\u00e1tumig", "tr": "Biti\u015f Tarihi"},
    "CSV Filter": {"hu": "CSV sz\u0171r\u0151", "tr": "CSV Filtresi"},
    "No Data": {"hu": "Nincs adat", "tr": "Veri yok"},
    # CMR section
    "Consignment Parties": {"hu": "K\u00fcldem\u00e9ny felek", "tr": "Sevkiyat Taraflar\u0131"},
    "Successive Carriers": {"hu": "Egym\u00e1st k\u00f6vet\u0151 fuvaroz\u00f3k", "tr": "Ard\u0131\u015f\u0131k Ta\u015f\u0131y\u0131c\u0131lar"},
    "CMR Waybill": {"hu": "CMR fuvarlev\u00e9l", "tr": "CMR Ta\u015f\u0131ma Senedi"},
    "Generating 4 copies...": {"hu": "4 p\u00e9ld\u00e1ny gener\u00e1l\u00e1sa...", "tr": "4 kopya olu\u015fturuluyor..."},
    "Issued by Carrier": {"hu": "Ki\u00e1ll\u00edtotta a fuvaroz\u00f3", "tr": "Ta\u015f\u0131y\u0131c\u0131 taraf\u0131ndan d\u00fczenlenmi\u015ftir"},
}

def translate(lang_code, translations):
    en = load_json(os.path.join(TRANS_DIR, "en.json"))
    en_flat = flatten(en)
    filepath = os.path.join(TRANS_DIR, f"{lang_code}.json")
    data = load_json(filepath)
    flat = flatten(data)
    changes = 0
    for k, en_v in en_flat.items():
        if not isinstance(en_v, str) or not en_v.strip():
            continue
        if k not in flat:
            continue
        v = flat[k]
        if not isinstance(v, str):
            continue
        if v != en_v:
            continue
        if en_v in translations and lang_code in translations[en_v]:
            tr = translations[en_v][lang_code]
            if tr and tr != en_v:
                flat[k] = tr
                changes += 1
    if changes > 0:
        new_data = unflatten(flat)
        save_json(filepath, new_data)
    return changes

for lang in ["hu", "tr"]:
    c = translate(lang, MORE_TRANSLATIONS)
    print(f"  {lang}.json: {c} new translations applied")
