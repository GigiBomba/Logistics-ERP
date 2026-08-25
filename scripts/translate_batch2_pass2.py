#!/usr/bin/env python3
"""Second pass: handle remaining untranslated values with targeted fixes."""
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

# Additional phrase maps for remaining untranslated values
# Key = English phrase, value = {lang: translation}

REMAINING_MAP = {
    # Common acronyms/values to treat as already-translated (keep as-is)
    "ERP": {"cs": "ERP", "pt": "ERP", "hu": "ERP", "tr": "ERP"},
    "EMAIL": {"cs": "EMAIL", "pt": "EMAIL", "hu": "EMAIL", "tr": "E-POSTA"},
    "ROLE": {"cs": "ROLE", "pt": "FUN\u00c7\u00c3O", "hu": "SZEREPK\u00d6R", "tr": "ROL"},
    "PASSWORD": {"cs": "HESLO", "pt": "SENHA", "hu": "JELSZ\u00d3", "tr": "\u015e\u0130FRE"},
    "LINK DRIVER": {"cs": "PROPOJIT \u0158IDI\u010cE", "pt": "VINCULAR MOTORISTA", "hu": "SOF\u0150R KAPCSOL\u00c1S", "tr": "S\u00dcR\u00dcC\u00dcY\u00dc BA\u011eLA"},
    "Role": {"cs": "Role", "pt": "Fun\u00e7\u00e3o", "hu": "Szerepk\u00f6r", "tr": "Rol"},
    "Dispatcher": {"cs": "Dispe\u010der", "pt": "Despachante", "hu": "Diszp\u00e9cser", "tr": "Dispatch"},
    "Email": {"cs": "Email", "pt": "Email", "hu": "Email", "tr": "E-posta"},
    "Excel": {"cs": "Excel", "pt": "Excel", "hu": "Excel", "tr": "Excel"},
    "Datum": {"cs": "Datum", "pt": "Data", "hu": "D\u00e1tum", "tr": "Tarih"},
    "Model:": {"cs": "Model:", "pt": "Modelo:", "hu": "Modell:", "tr": "Model:"},
    "Emailed": {"cs": "Odesl\u00e1no emailem", "pt": "Enviado por email", "hu": "Elk\u00fcldve emailben", "tr": "E-posta g\u00f6nderildi"},
    "Top 3": {"cs": "Top 3", "pt": "Top 3", "hu": "Top 3", "tr": "\u0130lk 3"},
    "Rest": {"cs": "Ostatn\u00ed", "pt": "Restante", "hu": "T\u00f6bbi", "tr": "Kalan"},
    "Finance": {"cs": "Finance", "pt": "Finan\u00e7as", "hu": "P\u00e9nz\u00fcgy", "tr": "Finans"},
    "Start": {"cs": "Start", "pt": "In\u00edcio", "hu": "Kezd\u00e9s", "tr": "Ba\u015flang\u0131\u00e7"},
    "Info": {"cs": "Info", "pt": "Info", "hu": "Info", "tr": "Bilgi"},
    "OK": {"cs": "OK", "pt": "OK", "hu": "OK", "tr": "Tamam"},
    "Total": {"cs": "Celkem", "pt": "Total", "hu": "\u00d6sszesen", "tr": "Toplam"},
    "Net": {"cs": "\u010cist\u00fd", "pt": "L\u00edquido", "hu": "Nett\u00f3", "tr": "Net"},
    "Telefon": {"cs": "Telefon", "pt": "Telefone", "hu": "Telefon", "tr": "Telefon"},
    "Filters": {"cs": "Filtry", "pt": "Filtros", "hu": "Sz\u0171r\u0151k", "tr": "Filtreler"},
    "Comment": {"cs": "Koment\u00e1\u0159", "pt": "Coment\u00e1rio", "hu": "Megjegyz\u00e9s", "tr": "Yorum"},
    "Set": {"cs": "Nastavit", "pt": "Definir", "hu": "Be\u00e1ll\u00edt", "tr": "Ayarla"},
    "Unlink": {"cs": "Odpojit", "pt": "Desvincular", "hu": "Lev\u00e1laszt", "tr": "Ba\u011flant\u0131y\u0131 kald\u0131r"},
    "Restore": {"cs": "Obnovit", "pt": "Restaurar", "hu": "Vissza\u00e1ll\u00edt", "tr": "Geri y\u00fckle"},
    "Pick": {"cs": "Vybrat", "pt": "Escolher", "hu": "V\u00e1laszt", "tr": "Se\u00e7"},
    "Browse": {"cs": "Proch\u00e1zet", "pt": "Procurar", "hu": "Tall\u00f3z", "tr": "G\u00f6z at"},
    "Load": {"cs": "Na\u010d\u00edst", "pt": "Carregar", "hu": "Bet\u00f6lt", "tr": "Y\u00fckle"},
    "Preview": {"cs": "N\u00e1hled", "pt": "Visualizar", "hu": "El\u0151n\u00e9zet", "tr": "\u00d6nizleme"},
    "Subtotal": {"cs": "Mezisou\u010det", "pt": "Subtotal", "hu": "R\u00e9sz\u00f6sszeg", "tr": "Ara toplam"},
    "Totals": {"cs": "Sou\u010dty", "pt": "Totais", "hu": "\u00d6sszegek", "tr": "Toplamlar"},
    "Fixed": {"cs": "Fixn\u00ed", "pt": "Fixo", "hu": "R\u00f6gz\u00edtett", "tr": "Sabit"},
    "BRANDING": {"cs": "BRANDING", "pt": "MARCA", "hu": "BRANDING", "tr": "MARKALA\u015eTIRMA"},
    "Unloading": {"cs": "Vykl\u00e1dka", "pt": "Descarregamento", "hu": "Kirakod\u00e1s", "tr": "Bo\u015faltma"},
    "Email:": {"cs": "Email:", "pt": "Email:", "hu": "Email:", "tr": "E-posta:"},
    "Proforma": {"cs": "Proforma", "pt": "Proforma", "hu": "Proforma", "tr": "Proforma"},
    "Proformas": {"cs": "Proformy", "pt": "Proformas", "hu": "Proform\u00e1k", "tr": "Proformalar"},
    "Signature": {"cs": "Podpis", "pt": "Assinatura", "hu": "Al\u00e1\u00edr\u00e1s", "tr": "\u0130mza"},
    "Stamp": {"cs": "Raz\u00edtko", "pt": "Carimbo", "hu": "B\u00e9lyegz\u0151", "tr": "Damga"},
    "Logo": {"cs": "Logo", "pt": "Logo", "hu": "Log\u00f3", "tr": "Logo"},
    "Total:": {"cs": "Celkem:", "pt": "Total:", "hu": "\u00d6sszesen:", "tr": "Toplam:"},
    "KPIs": {"cs": "KPI", "pt": "KPIs", "hu": "KPI-k", "tr": "KPI'lar"},
    "VAT:": {"cs": "DPH:", "pt": "IVA:", "hu": "\u00c1FA:", "tr": "KDV:"},
    "Limit: \u20ac{:,}": {"cs": "Limit: \u20ac{:,}", "pt": "Limite: \u20ac{:,}", "hu": "Limit: \u20ac{:,}", "tr": "Limit: \u20ac{:,}"},
    "Credit Limit (EUR)": {"cs": "\u00dav\u011brov\u00fd limit (EUR)", "pt": "Limite de Cr\u00e9dito (EUR)", "hu": "Hitelkeret (EUR)", "tr": "Kredi Limiti (EUR)"},
    "Default Rate/km": {"cs": "V\u00fdchoz\u00ed sazba/km", "pt": "Taxa Padr\u00e3o/km", "hu": "Alap\u00e9rtelmezett d\u00edj/km", "tr": "Varsay\u0131lan Oran/km"},
    "Rating (1-5)": {"cs": "Hodnocen\u00ed (1-5)", "pt": "Avalia\u00e7\u00e3o (1-5)", "hu": "\u00c9rt\u00e9kel\u00e9s (1-5)", "tr": "Puan (1-5)"},
    "Contact Person": {"cs": "Kontaktn\u00ed osoba", "pt": "Pessoa de Contato", "hu": "Kapcsolattart\u00f3", "tr": "\u0130leti\u015fim Ki\u015fisi"},
    "Outstanding Invoices": {"cs": "Neuhrazen\u00e9 faktury", "pt": "Faturas Pendentes", "hu": "Kintlev\u0151 sz\u00e1ml\u00e1k", "tr": "Bekleyen Faturalar"},
    "Total Trips": {"cs": "Celkem j\u00edzd", "pt": "Total de Viagens", "hu": "\u00d6sszes \u00fat", "tr": "Toplam Seyahat"},
    "Trips (30d)": {"cs": "J\u00edzdy (30d)", "pt": "Viagens (30d)", "hu": "Utak (30n)", "tr": "Seyahatler (30g)"},
    "Avg Profit/Trip": {"cs": "Pr\u016fm. zisk/j\u00edzda", "pt": "Lucro M\u00e9dio/Viagem", "hu": "\u00c1tl. nyeres\u00e9g/\u00fat", "tr": "Ort. K\u00e2r/Seyahat"},
    "Contacts": {"cs": "Kontakty", "pt": "Contatos", "hu": "Kapcsolatok", "tr": "\u0130leti\u015fimler"},
    "Revenue Trend": {"cs": "Trend p\u0159\u00edjm\u016f", "pt": "Tend\u00eancia de Receita", "hu": "Bev\u00e9tel trend", "tr": "Gelir Trendi"},
    "Activity Timeline": {"cs": "\u010casov\u00e1 osa aktivity", "pt": "Linha do Tempo de Atividade", "hu": "Aktivit\u00e1s id\u0151vonal", "tr": "Aktivite Zaman \u00c7izelgesi"},
    "Merge Clients": {"cs": "Slou\u010dit klienty", "pt": "Mesclar Clientes", "hu": "\u00dcgyfelek egyes\u00edt\u00e9se", "tr": "M\u00fc\u015fterileri Birle\u015ftir"},
    "Merge": {"cs": "Slou\u010dit", "pt": "Mesclar", "hu": "Egyes\u00edt", "tr": "Birle\u015ftir"},
    "Clients exported successfully.": {"cs": "Klienti \u00fasp\u011b\u0161n\u011b exportov\u00e1ni.", "pt": "Clientes exportados com sucesso.", "hu": "\u00dcgyfelek sikeresen export\u00e1lva.", "tr": "M\u00fc\u015fteriler ba\u015far\u0131yla d\u0131\u015fa aktar\u0131ld\u0131."},
    "Instructions & Reservations": {"cs": "Pokyny a rezervace", "pt": "Instru\u00e7\u00f5es e Reservas", "hu": "Utas\u00edt\u00e1sok \u00e9s foglal\u00e1sok", "tr": "Talimatlar ve Rezervasyonlar"},
    "ADR Dangerous Goods": {"cs": "ADR Nebezpe\u010dn\u00e9 zbo\u017e\u00ed", "pt": "Mercadorias Perigosas ADR", "hu": "ADR Vesz\u00e9lyes \u00e1ruk", "tr": "ADR Tehlikeli Mallar"},
    "Signature & Stamp": {"cs": "Podpis a raz\u00edtko", "pt": "Assinatura e Carimbo", "hu": "Al\u00e1\u00edr\u00e1s \u00e9s b\u00e9lyegz\u0151", "tr": "\u0130mza ve Damga"},
    "not generated": {"cs": "nevygenerov\u00e1no", "pt": "n\u00e3o gerado", "hu": "nem gener\u00e1lva", "tr": "olu\u015fturulmad\u0131"},
    "Generated Copies": {"cs": "Vygenerovan\u00e9 kopie", "pt": "C\u00f3pias Geradas", "hu": "Gener\u00e1lt p\u00e9ld\u00e1nyok", "tr": "Olu\u015fturulan Kopyalar"},
    "generated": {"cs": "vygenerov\u00e1no", "pt": "gerado", "hu": "gener\u00e1lva", "tr": "olu\u015fturuldu"},
    "Receipt": {"cs": "\u00da\u010dtenka", "pt": "Recibo", "hu": "Nyugta", "tr": "Makbuz"},
    "Auto-Fill": {"cs": "Automatick\u00e9 vypln\u011bn\u00ed", "pt": "Preenchimento Autom\u00e1tico", "hu": "Automatikus kit\u00f6lt\u00e9s", "tr": "Otomatik Doldur"},
    "Tax%": {"cs": "Da\u0148%", "pt": "Imposto%", "hu": "Ad\u00f3%", "tr": "Vergi%"},
    "Grand Total": {"cs": "Celkov\u00fd sou\u010det", "pt": "Total Geral", "hu": "V\u00e9g\u00f6sszeg", "tr": "Genel Toplam"},
    "Financial Controls": {"cs": "Finan\u010dn\u00ed kontroly", "pt": "Controles Financeiros", "hu": "P\u00e9nz\u00fcgyi ellen\u0151rz\u00e9sek", "tr": "Finansal Kontroller"},
    "Branding": {"cs": "Branding", "pt": "Marca", "hu": "Branding", "tr": "Markala\u015ft\u0131rma"},
    "Generate PDF": {"cs": "Generovat PDF", "pt": "Gerar PDF", "hu": "PDF gener\u00e1l\u00e1sa", "tr": "PDF Olu\u015ftur"},
    "Load Draft": {"cs": "Na\u010d\u00edst koncept", "pt": "Carregar Rascunho", "hu": "Piszkozat bet\u00f6lt\u00e9se", "tr": "Taslak Y\u00fckle"},
    "Draft Saved": {"cs": "Koncept ulo\u017een", "pt": "Rascunho Salvo", "hu": "Piszkozat mentve", "tr": "Taslak Kaydedildi"},
    "Draft Loaded": {"cs": "Koncept na\u010dten", "pt": "Rascunho Carregado", "hu": "Piszkozat bet\u00f6ltve", "tr": "Taslak Y\u00fcklendi"},
    "Draft '{}' saved successfully.": {"cs": "Koncept '{}' \u00fasp\u011b\u0161n\u011b ulo\u017een.", "pt": "Rascunho '{}' salvo com sucesso.", "hu": "Piszkozat '{}' sikeresen mentve.", "tr": "'{}' tasla\u011f\u0131 ba\u015far\u0131yla kaydedildi."},
    "Draft '{}' loaded successfully.": {"cs": "Koncept '{}' \u00fasp\u011b\u0161n\u011b na\u010dten.", "pt": "Rascunho '{}' carregado com sucesso.", "hu": "Piszkozat '{}' sikeresen bet\u00f6ltve.", "tr": "'{}' tasla\u011f\u0131 ba\u015far\u0131yla y\u00fcklendi."},
    "Transport services": {"cs": "P\u0159epravn\u00ed slu\u017eby", "pt": "Servi\u00e7os de transporte", "hu": "Sz\u00e1ll\u00edt\u00e1si szolg\u00e1ltat\u00e1sok", "tr": "Ta\u015f\u0131ma hizmetleri"},
    "Recipient Email": {"cs": "Email p\u0159\u00edjemce", "pt": "Email do Destinat\u00e1rio", "hu": "C\u00edmzett email", "tr": "Al\u0131c\u0131 E-posta"},
    "Unloading Stops": {"cs": "M\u00edsta vykl\u00e1dky", "pt": "Paradas de Descarga", "hu": "Kirakod\u00e1si meg\u00e1ll\u00f3k", "tr": "Bo\u015faltma Duraklar\u0131"},
    "Line Items": {"cs": "\u0158\u00e1dkov\u00e9 polo\u017eky", "pt": "Itens de Linha", "hu": "Sor t\u00e9telek", "tr": "Sat\u0131r \u00d6\u011feleri"},
    "Branch / Office": {"cs": "Pobo\u010dka / kancel\u00e1\u0159", "pt": "Filial / Escrit\u00f3rio", "hu": "Fi\u00f3k / Iroda", "tr": "\u015eube / Ofis"},
    "Internal Mode": {"cs": "Intern\u00ed re\u017eim", "pt": "Modo Interno", "hu": "Bels\u0151 m\u00f3d", "tr": "Dahili Mod"},
    "Proforma #": {"cs": "Proforma #", "pt": "Proforma #", "hu": "Proforma #", "tr": "Proforma #"},
    "Linked Documents": {"cs": "Propojen\u00e9 dokumenty", "pt": "Documentos Vinculados", "hu": "Kapcsolt dokumentumok", "tr": "Ba\u011fl\u0131 Belgeler"},
    "Include linked CMRs and invoices": {"cs": "Zahrnout propojen\u00e9 CMR a faktury", "pt": "Incluir CMRs e faturas vinculadas", "hu": "Kapcsolt CMR-ek \u00e9s sz\u00e1ml\u00e1k bele\u00e9rtve", "tr": "Ba\u011fl\u0131 CMR'lar\u0131 ve faturalar\u0131 dahil et"},
    "Email sent successfully.": {"cs": "Email \u00fasp\u011b\u0161n\u011b odesl\u00e1n.", "pt": "Email enviado com sucesso.", "hu": "Email sikeresen elk\u00fcldve.", "tr": "E-posta ba\u015far\u0131yla g\u00f6nderildi."},
    "Gross Weight (kg)": {"cs": "Hrub\u00e1 hmotnost (kg)", "pt": "Peso Bruto (kg)", "hu": "Brut\u00f3 s\u00faly (kg)", "tr": "Br\u00fct A\u011f\u0131rl\u0131k (kg)"},
    "I am the Consignor (Sender)": {"cs": "Jsem odes\u00edlatel", "pt": "Sou o Consignador (Remetente)", "hu": "En vagyok a felad\u00f3", "tr": "Ben g\u00f6ndericiyim"},
    "I am the Consignee (Receiver)": {"cs": "Jsem p\u0159\u00edjemce", "pt": "Sou o Consignat\u00e1rio (Destinat\u00e1rio)", "hu": "En vagyok a c\u00edmzett", "tr": "Ben al\u0131c\u0131y\u0131m"},
    "Consignor / Shipper": {"cs": "Odes\u00edlatel / P\u0159epravce", "pt": "Consignador / Remetente", "hu": "Felad\u00f3 / Sz\u00e1ll\u00edt\u00f3", "tr": "G\u00f6nderici / Nakliyeci"},
    "Consignee": {"cs": "P\u0159\u00edjemce", "pt": "Consignat\u00e1rio", "hu": "C\u00edmzett", "tr": "Al\u0131c\u0131"},
    "Documents attached": {"cs": "P\u0159ilo\u017een\u00e9 dokumenty", "pt": "Documentos anexados", "hu": "Csatolt dokumentumok", "tr": "Ekli belgeler"},
    "Carrier": {"cs": "Dopravce", "pt": "Transportadora", "hu": "Sz\u00e1ll\u00edtm\u00e1nyoz\u00f3", "tr": "Ta\u015f\u0131y\u0131c\u0131"},
    "Place and date of issue": {"cs": "M\u00edsto a datum vystaven\u00ed", "pt": "Local e data de emiss\u00e3o", "hu": "Ki\u00e1ll\u00edt\u00e1s helye \u00e9s d\u00e1tuma", "tr": "D\u00fczenleme yeri ve tarihi"},
    "Transport document": {"cs": "P\u0159epravn\u00ed doklad", "pt": "Documento de transporte", "hu": "Sz\u00e1ll\u00edt\u00e1si okm\u00e1ny", "tr": "Ta\u015f\u0131ma belgesi"},
    "Overall Health": {"cs": "Celkov\u00fd stav", "pt": "Sa\u00fade Geral", "hu": "\u00c1ltal\u00e1nos \u00e1llapot", "tr": "Genel Durum"},
    "Compliance": {"cs": "Compliance", "pt": "Conformidade", "hu": "Megfelel\u0151s\u00e9g", "tr": "Uyum"},
    "Recurring Issues": {"cs": "Opakuj\u00edc\u00ed se probl\u00e9my", "pt": "Problemas Recorrentes", "hu": "Ism\u00e9tl\u0151d\u0151 probl\u00e9m\u00e1k", "tr": "Tekrarlayan Sorunlar"},
    "Downtime": {"cs": "Prostoj", "pt": "Tempo de inatividade", "hu": "\u00c1ll\u00e1sid\u0151", "tr": "Kesinti"},
    "Interval (days)": {"cs": "Interval (dn\u00ed)", "pt": "Intervalo (dias)", "hu": "Intervallum (nap)", "tr": "Aral\u0131k (g\u00fcn)"},
    " km": {"cs": " km", "pt": " km", "hu": " km", "tr": " km"},
    "Predictions": {"cs": "Predikce", "pt": "Previs\u00f5es", "hu": "El\u0151rejelz\u00e9sek", "tr": "Tahminler"},
    "Prev": {"cs": "P\u0159edchoz\u00ed", "pt": "Anterior", "hu": "El\u0151z\u0151", "tr": "\u00d6nceki"},
    "Updated": {"cs": "Aktualizov\u00e1no", "pt": "Atualizado", "hu": "Friss\u00edtve", "tr": "G\u00fcncellendi"},
    "Refresh Score": {"cs": "Obnovit sk\u00f3re", "pt": "Atualizar Pontua\u00e7\u00e3o", "hu": "Pontsz\u00e1m friss\u00edt\u00e9se", "tr": "Puan\u0131 Yenile"},
    "Status Ok": {"cs": "Stav OK", "pt": "Status OK", "hu": "\u00c1llapot OK", "tr": "Durum Tamam"},
    "Calibration": {"cs": "Kalibrace", "pt": "Calibra\u00e7\u00e3o", "hu": "Kalibr\u00e1l\u00e1s", "tr": "Kalibrasyon"},
    "Days": {"cs": "Dny", "pt": "Dias", "hu": "Napok", "tr": "G\u00fcnler"},
    "Records": {"cs": "Z\u00e1znamy", "pt": "Registros", "hu": "Rekordok", "tr": "Kay\u0131tlar"},
    "Metric Compliance": {"cs": "Metric Compliance", "pt": "Conformidade de M\u00e9trica", "hu": "Mutat\u00f3 megfelel\u0151s\u00e9g", "tr": "Metrik Uyum"},
    "Metric Downtime": {"cs": "Metric Downtime", "pt": "Tempo de Inatividade de M\u00e9trica", "hu": "Mutat\u00f3 \u00e1ll\u00e1sid\u0151", "tr": "Metrik Kesinti"},
    "Metric Recurring": {"cs": "Metric Recurring", "pt": "Recorrente de M\u00e9trica", "hu": "Mutat\u00f3 ism\u00e9tl\u0151d\u0151", "tr": "Metrik Tekrarlayan"},
    "Metric Score": {"cs": "Metric Score", "pt": "Pontua\u00e7\u00e3o de M\u00e9trica", "hu": "Mutat\u00f3 pontsz\u00e1m", "tr": "Metrik Puan\u0131"},
    "Action Maint": {"cs": "Akce \u00fadr\u017eba", "pt": "A\u00e7\u00e3o Manuten\u00e7\u00e3o", "hu": "Karbantart\u00e1s m\u0171velet", "tr": "Bak\u0131m \u0130\u015flemi"},
    "Action Remind": {"cs": "Akce p\u0159ipomenout", "pt": "A\u00e7\u00e3o Lembrar", "hu": "Eml\u00e9keztet\u0151 m\u0171velet", "tr": "Hat\u0131rlatma \u0130\u015flemi"},
    "Action Resolve": {"cs": "Akce vy\u0159e\u0161it", "pt": "A\u00e7\u00e3o Resolver", "hu": "Megold\u00e1s m\u0171velet", "tr": "\u00c7\u00f6z\u00fcm \u0130\u015flemi"},
    "Col Notes": {"cs": "Pozn\u00e1mky", "pt": "Observa\u00e7\u00f5es", "hu": "Megjegyz\u00e9sek", "tr": "Notlar"},
    "Col Provider": {"cs": "Poskytovatel", "pt": "Fornecedor", "hu": "Szolg\u00e1ltat\u00f3", "tr": "Sa\u011flay\u0131c\u0131"},
    "Critical Health": {"cs": "Kritick\u00fd stav", "pt": "Sa\u00fade Cr\u00edtica", "hu": "Kritikus \u00e1llapot", "tr": "Kritik Durum"},
    "Flash Maint Scheduled": {"cs": "Pl\u00e1novan\u00e1 \u00fadr\u017eba", "pt": "Manuten\u00e7\u00e3o Agendada", "hu": "\u00dctemezett karbantart\u00e1s", "tr": "Planlanm\u0131\u015f Bak\u0131m"},
    "Tab Health": {"cs": "Z\u00e1lo\u017eka Stav", "pt": "Guia Sa\u00fade", "hu": "F\u00fcl \u00c1llapot", "tr": "Sekme Durum"},
    "Tab Schedules": {"cs": "Z\u00e1lo\u017eka Rozvrhy", "pt": "Guias Agendas", "hu": "F\u00fcl \u00dctemez\u00e9sek", "tr": "Sekme Programlar"},
    "Maintenance schedules and health monitoring": {"cs": "Pl\u00e1ny \u00fadr\u017eby a sledov\u00e1n\u00ed stavu", "pt": "Agendas de manuten\u00e7\u00e3o e monitoramento de sa\u00fade", "hu": "Karbantart\u00e1si \u00fctemez\u00e9sek \u00e9s \u00e1llapotfigyel\u00e9s", "tr": "Bak\u0131m programlar\u0131 ve durum izleme"},
    "Calibration": {"cs": "Kalibrace", "pt": "Calibra\u00e7\u00e3o", "hu": "Kalibr\u00e1l\u00e1s", "tr": "Kalibrasyon"},
    "DDD / TGD / other tachograph files": {"cs": "DDD / TGD / jin\u00e9 tachografick\u00e9 soubory", "pt": "DDD / TGD / outros arquivos de tac\u00f3grafo", "hu": "DDD / TGD / egy\u00e9b tachogr\u00e1f f\u00e1jlok", "tr": "DDD / TGD / di\u011fer takograf dosyalar\u0131"},
    "Fleet maintenance costs and trends": {"cs": "N\u00e1klady na \u00fadr\u017ebu flotily a trendy", "pt": "Custos de manuten\u00e7\u00e3o da frota e tend\u00eancias", "hu": "Flotta karbantart\u00e1si k\u00f6lts\u00e9gek \u00e9s trendek", "tr": "Filo bak\u0131m maliyetleri ve trendler"},
    "Action Trip": {"cs": "Akce j\u00edzda", "pt": "A\u00e7\u00e3o Viagem", "hu": "\u00dat m\u0171velet", "tr": "Seyahat \u0130\u015flemi"},
    "Action Truck": {"cs": "Akce vozidlo", "pt": "A\u00e7\u00e3o Caminh\u00e3o", "hu": "Kamion m\u0171velet", "tr": "Kamyon \u0130\u015flemi"},
    "Alert S": {"cs": "Upozorn\u011bn\u00ed", "pt": "Alerta", "hu": "Riaszt\u00e1s", "tr": "Uyar\u0131"},
    "Alert Plural": {"cs": "Upozorn\u011bn\u00ed", "pt": "Alertas", "hu": "Riaszt\u00e1sok", "tr": "Uyar\u0131lar"},
    "Col Cost": {"cs": "N\u00e1klady", "pt": "Custo", "hu": "K\u00f6lts\u00e9g", "tr": "Maliyet"},
    "Col Date": {"cs": "Datum", "pt": "Data", "hu": "D\u00e1tum", "tr": "Tarih"},
    "Col Km": {"cs": "Km", "pt": "Km", "hu": "Km", "tr": "Km"},
    "Col Type": {"cs": "Typ", "pt": "Tipo", "hu": "T\u00edpus", "tr": "T\u00fcr"},
    "Confirm Delete Msg": {"cs": "Potvrdit smaz\u00e1n\u00ed zpr\u00e1vy", "pt": "Mensagem de confirma\u00e7\u00e3o de exclus\u00e3o", "hu": "T\u00f6rl\u00e9s meger\u0151s\u00edt\u00e9se \u00fczenet", "tr": "Silme onay mesaj\u0131"},
    "Confirm Delete Title": {"cs": "Potvrdit smaz\u00e1n\u00ed n\u00e1zev", "pt": "T\u00edtulo de confirma\u00e7\u00e3o de exclus\u00e3o", "hu": "T\u00f6rl\u00e9s meger\u0151s\u00edt\u00e9se c\u00edm", "tr": "Silme onay ba\u015fl\u0131\u011f\u0131"},
    "Critical Count": {"cs": "Kritick\u00fd po\u010det", "pt": "Contagem Cr\u00edtica", "hu": "Kritikus sz\u00e1m", "tr": "Kritik Say\u0131"},
    "Days Left": {"cs": "Zb\u00fdv\u00e1 dn\u00ed", "pt": "Dias Restantes", "hu": "H\u00e1tral\u00e9v\u0151 napok", "tr": "Kalan G\u00fcn"},
    "Due By Date": {"cs": "Splatn\u00e9 do", "pt": "Vencimento em", "hu": "Hat\u00e1rid\u0151", "tr": "Son Tarih"},
    "Error Generic": {"cs": "Obecn\u00e1 chyba", "pt": "Erro Gen\u00e9rico", "hu": "\u00c1ltal\u00e1nos hiba", "tr": "Genel Hata"},
    "Export Success": {"cs": "Export \u00fasp\u011b\u0161n\u00fd", "pt": "Exportado com sucesso", "hu": "Export\u00e1l\u00e1s sikeres", "tr": "D\u0131\u015fa aktarma ba\u015far\u0131l\u0131"},
    "Export Title": {"cs": "N\u00e1zev exportu", "pt": "T\u00edtulo de Exporta\u00e7\u00e3o", "hu": "Export\u00e1l\u00e1s c\u00edm", "tr": "D\u0131\u015fa Aktarma Ba\u015fl\u0131\u011f\u0131"},
    "Filter Label": {"cs": "Popisek filtru", "pt": "R\u00f3tulo do Filtro", "hu": "Sz\u0171r\u0151 c\u00edmke", "tr": "Filtre Etiketi"},
    "Flash Reminder": {"cs": "P\u0159ipomenut\u00ed", "pt": "Lembrete", "hu": "Eml\u00e9keztet\u0151", "tr": "Hat\u0131rlatma"},
    "Flash Trip Copied": {"cs": "J\u00edzda zkop\u00edrov\u00e1na", "pt": "Viagem copiada", "hu": "\u00dat m\u00e1solva", "tr": "Seyahat kopyaland\u0131"},
    "Flash Truck Copied": {"cs": "Vozidlo zkop\u00edrov\u00e1no", "pt": "Caminh\u00e3o copiado", "hu": "Kamion m\u00e1solva", "tr": "Kamyon kopyaland\u0131"},
    "Form Cost": {"cs": "N\u00e1klady", "pt": "Custo", "hu": "K\u00f6lts\u00e9g", "tr": "Maliyet"},
    "Form Date": {"cs": "Datum", "pt": "Data", "hu": "D\u00e1tum", "tr": "Tarih"},
    "Form Km": {"cs": "Km", "pt": "Km", "hu": "Km", "tr": "Km"},
    "Header": {"cs": "Z\u00e1hlav\u00ed", "pt": "Cabe\u00e7alho", "hu": "Fejl\u00e9c", "tr": "\u00dcstbilgi"},
    "Info Count": {"cs": "Po\u010det informac\u00ed", "pt": "Contagem de informa\u00e7\u00f5es", "hu": "Inform\u00e1ci\u00f3k sz\u00e1ma", "tr": "Bilgi say\u0131s\u0131"},
    "Billed": {"cs": "Fakturov\u00e1no", "pt": "Faturado", "hu": "Sz\u00e1ml\u00e1zva", "tr": "Faturaland\u0131"},
    "Deactivate '{name}'?": {"cs": "Deaktivovat '{name}'?", "pt": "Desativar '{name}'?", "hu": "Deaktiv\u00e1lja '{name}'?", "tr": "'{name}' devre d\u0131\u015f\u0131 b\u0131rak\u0131ls\u0131n m\u0131?"},
    "Sales": {"cs": "Prodej", "pt": "Vendas", "hu": "\u00c9rt\u00e9kes\u00edt\u00e9s", "tr": "Sat\u0131\u015f"},
    "Button Email": {"cs": "Tla\u010d\u00edtko Email", "pt": "Bot\u00e3o Email", "hu": "Email gomb", "tr": "E-posta D\u00fc\u011fmesi"},
    "Generate CMR Waybill": {"cs": "Generovat CMR n\u00e1kladn\u00ed list", "pt": "Gerar Conhecimento CMR", "hu": "CMR fuvarlev\u00e9l gener\u00e1l\u00e1sa", "tr": "CMR Ta\u015f\u0131ma Senedi Olu\u015ftur"},
    "Generate CMR": {"cs": "Generovat CMR", "pt": "Gerar CMR", "hu": "CMR gener\u00e1l\u00e1s", "tr": "CMR Olu\u015ftur"},
    "Kpi Avg Trips": {"cs": "Pr\u016fm. po\u010det j\u00edzd", "pt": "M\u00e9dia de Viagens", "hu": "\u00c1tlagos utak", "tr": "Ort. Seyahatler"},
    "Kpi Total Drivers": {"cs": "Celkem \u0159idi\u010d\u016f", "pt": "Total de Motoristas", "hu": "\u00d6sszes sof\u0151r", "tr": "Toplam S\u00fcr\u00fcc\u00fc"},
    "Kpi Total Violations": {"cs": "Celkem poru\u0161en\u00ed", "pt": "Total de Viola\u00e7\u00f5es", "hu": "\u00d6sszes szab\u00e1lys\u00e9rt\u00e9s", "tr": "Toplam \u0130hlal"},
    "Revenue Vs Profit Scatter": {"cs": "Bodov\u00fd graf v\u00fdnos\u016f vs zisku", "pt": "Dispers\u00e3o de Receita vs Lucro", "hu": "Bev\u00e9tel vs nyeres\u00e9g sz\u00f3r\u00e1s", "tr": "Gelir vs K\u00e2r Da\u011f\u0131l\u0131m\u0131"},
    "Export JSON": {"cs": "Export JSON", "pt": "Exportar JSON", "hu": "JSON export\u00e1l\u00e1s", "tr": "JSON D\u0131\u015fa Aktar"},
    "Import CSV": {"cs": "Import CSV", "pt": "Importar CSV", "hu": "CSV import\u00e1l\u00e1s", "tr": "CSV \u0130\u00e7e Aktar"},
    "Email Body": {"cs": "T\u011blo emailu", "pt": "Corpo do Email", "hu": "Email t\u00f6rzs", "tr": "E-posta G\u00f6vdesi"},
    "Email Subject": {"cs": "P\u0159edm\u011bt emailu", "pt": "Assunto do Email", "hu": "Email t\u00e1rgya", "tr": "E-posta Konusu"},
    "Email Failed": {"cs": "Email selhal", "pt": "Falha no Email", "hu": "Email sikertelen", "tr": "E-posta Ba\u015far\u0131s\u0131z"},
    "Email Success": {"cs": "Email \u00fasp\u011b\u0161n\u00fd", "pt": "Email Enviado", "hu": "Email sikeres", "tr": "E-posta Ba\u015far\u0131l\u0131"},
    "Smtp Not Configured": {"cs": "SMTP nen\u00ed nakonfigurov\u00e1no", "pt": "SMTP N\u00e3o Configurado", "hu": "SMTP nincs konfigur\u00e1lva", "tr": "SMTP Yap\u0131land\u0131r\u0131lmam\u0131\u015f"},
    "Default Client": {"cs": "V\u00fdchoz\u00ed klient", "pt": "Cliente Padr\u00e3o", "hu": "Alap\u00e9rtelmezett \u00fcgyf\u00e9l", "tr": "Varsay\u0131lan M\u00fc\u015fteri"},
    "Net 30": {"cs": "Net 30", "pt": "L\u00edquido 30", "hu": "Nett\u00f3 30", "tr": "Net 30"},
    "Net 15": {"cs": "Net 15", "pt": "L\u00edquido 15", "hu": "Nett\u00f3 15", "tr": "Net 15"},
    "Net 60": {"cs": "Net 60", "pt": "L\u00edquido 60", "hu": "Nett\u00f3 60", "tr": "Net 60"},
    "Button Email": {"cs": "Tla\u010d\u00edtko Email", "pt": "Bot\u00e3o Email", "hu": "Email gomb", "tr": "E-posta D\u00fc\u011fmesi"},
    "Clear Filters": {"cs": "Vymazat filtry", "pt": "Limpar Filtros", "hu": "Sz\u0171r\u0151k t\u00f6rl\u00e9se", "tr": "Filtreleri Temizle"},
    "Email sent successfully.": {"cs": "Email \u00fasp\u011b\u0161n\u011b odesl\u00e1n.", "pt": "Email enviado com sucesso.", "hu": "Email sikeresen elk\u00fcldve.", "tr": "E-posta ba\u015far\u0131yla g\u00f6nderildi."},
    "Vehicles": {"cs": "Vozidla", "pt": "Ve\u00edculos", "hu": "J\u00e1rm\u0171vek", "tr": "Ara\u00e7lar"},
    "Already linked.": {"cs": "Ji\u017e propojeno.", "pt": "J\u00e1 vinculado.", "hu": "M\u00e1r kapcsolva.", "tr": "Zaten ba\u011fl\u0131."},
    "Extracted": {"cs": "Extrahov\u00e1no", "pt": "Extra\u00eddo", "hu": "Kinyerve", "tr": "Ay\u0131kland\u0131"},
    "Re-run OCR": {"cs": "Znovu spustit OCR", "pt": "Executar OCR novamente", "hu": "OCR \u00fajrafuttat\u00e1sa", "tr": "OCR'yi yeniden \u00e7al\u0131\u015ft\u0131r"},
    "OCR complete": {"cs": "OCR dokon\u010deno", "pt": "OCR conclu\u00eddo", "hu": "OCR k\u00e9sz", "tr": "OCR tamamland\u0131"},
    "Versions:": {"cs": "Verze:", "pt": "Vers\u00f5es:", "hu": "Verzi\u00f3k:", "tr": "S\u00fcr\u00fcmler:"},
    "Google Maps": {"cs": "Google Mapy", "pt": "Google Maps", "hu": "Google T\u00e9rk\u00e9p", "tr": "Google Haritalar"},
    "Total (EUR)": {"cs": "Celkem (EUR)", "pt": "Total (EUR)", "hu": "\u00d6sszesen (EUR)", "tr": "Toplam (EUR)"},
    "Set at least one provider": {"cs": "Nastavte alespo\u0148 jednoho poskytovatele", "pt": "Defina pelo menos um provedor", "hu": "Legal\u00e1bb egy szolg\u00e1ltat\u00f3t adjon meg", "tr": "En az bir sa\u011flay\u0131c\u0131 belirleyin"},
    " seconds": {"cs": " sekund", "pt": " segundos", "hu": " m\u00e1sodperc", "tr": " saniye"},
}

# Also add remaining HU/TR specific translations not in the main dict
# These are phrases that appear in the HU/TR output

HU_EXTRA = {
    "Calculate a route to see details.": "Sz\u00e1m\u00edtson ki egy \u00fatvonalat a r\u00e9szletek megtekint\u00e9s\u00e9hez.",
    "Add to Dispatch": "Hozz\u00e1ad\u00e1s a diszp\u00e9cserhez",
    "Send to Calculator": "K\u00fcld\u00e9s a sz\u00e1mol\u00f3g\u00e9pbe",
    "Client Name": "\u00dcgyf\u00e9l neve",
    "No saved route ID": "Nincs mentett \u00fatvonal azonos\u00edt\u00f3",
    "Start Date": "Kezd\u0151 d\u00e1tum",
    "Stop {n}": "Meg\u00e1ll\u00f3 {n}",
    "Trip Created": "\u00dat l\u00e9trehozva",
    "Recommended": "Aj\u00e1nlott",
    "Fastest": "Leggyorsabb",
    "Cheapest": "Legolcs\u00f3bb",
    "Safest": "Legbiztons\u00e1gosabb",
    "Shortest": "Legr\u00f6videbb",
    "Click map to add stop": "Kattintson a t\u00e9rk\u00e9pre a meg\u00e1ll\u00f3 hozz\u00e1ad\u00e1s\u00e1hoz",
    "Route loaded": "\u00datvonal bet\u00f6ltve",
    "Route Options": "\u00datvonal opci\u00f3k",
    "Plan multi-stop routes with cost estimation": "T\u00f6bbmeg\u00e1ll\u00f3s \u00fatvonalak tervez\u00e9se k\u00f6lts\u00e9gbecsl\u00e9ssel",
    "Route Planner": "\u00datvonaltervez\u0151",
    "Share Route": "\u00datvonal megoszt\u00e1sa",
    "Share link": "Link megoszt\u00e1sa",
    "Copy": "M\u00e1sol\u00e1s",
    "Export File": "F\u00e1jl export\u00e1l\u00e1sa",
    "Save & Open Folder": "Ment\u00e9s \u00e9s mappa megnyit\u00e1sa",
    "Copied!": "M\u00e1solva!",
    "Clipboard unavailable": "V\u00e1g\u00f3lap nem el\u00e9rhet\u0151",
    "Saved: {path}": "Mentve: {path}",
    "Calculate Route": "\u00datvonal sz\u00e1m\u00edt\u00e1sa",
    "Distance": "T\u00e1vols\u00e1g",
    "Duration": "Id\u0151tartam",
    "Recalculate": "\u00dajrasz\u00e1m\u00edt\u00e1s",
    "Archive": "Archiv\u00e1l\u00e1s",
    "Export JSON": "JSON export\u00e1l\u00e1s",
    "Export CSV": "CSV export\u00e1l\u00e1s",
    "Compare": "\u00d6sszehasonl\u00edt\u00e1s",
    "Loading map...": "T\u00e9rk\u00e9p bet\u00f6lt\u00e9se...",
    "Filter by truck": "Sz\u0171r\u00e9s kamion szerint",
    "Filter by Truck": "Sz\u0171r\u00e9s kamion szerint",
    "Confirm Archive": "Archiv\u00e1l\u00e1s meger\u0151s\u00edt\u00e9se",
    "Archive these routes?": "Archiv\u00e1lja ezeket az \u00fatvonalakat?",
    "Confirm Delete": "T\u00f6rl\u00e9s meger\u0151s\u00edt\u00e9se",
    "Delete these routes?": "T\u00f6rli ezeket az \u00fatvonalakat?",
    "Routes exported successfully.": "\u00datvonalak sikeresen export\u00e1lva.",
    "Routes recalculated successfully.": "\u00datvonalak sikeresen \u00fajrasz\u00e1m\u00edtva.",
    "Search routes...": "\u00datvonalak keres\u00e9se...",
    "Select truck...": "Kamion kiv\u00e1laszt\u00e1sa...",
    "Review and manage saved routes": "Mentett \u00fatvonalak \u00e1ttekint\u00e9se \u00e9s kezel\u00e9se",
    "Route History": "\u00datvonal el\u0151zm\u00e9nyek",
    "Active:": "Akt\u00edv:",
    "Archived:": "Archiv\u00e1lt:",
    "Date:": "D\u00e1tum:",
    "Truck:": "Kamion:",
    "Distance:": "T\u00e1vols\u00e1g:",
    "Duration:": "Id\u0151tartam:",
    "Fleet Tracking": "Flotta k\u00f6vet\u00e9s",
    "Tracking Platform": "K\u00f6vet\u0151 platform",
    "Platform not configured": "Platform nincs konfigur\u00e1lva",
    "API Token": "API token",
    "Server URL": "Szerver URL",
    "Account / Subdomain": "Fi\u00f3k / aldomain",
    "ID Field": "Azonos\u00edt\u00f3 mez\u0151",
    "Latitude Field": "F\u00f6ldrajzi sz\u00e9less\u00e9g mez\u0151",
    "Longitude Field": "F\u00f6ldrajzi hossz\u00fas\u00e1g mez\u0151",
    "Not Configured": "Nincs konfigur\u00e1lva",
    "Positions JSON Path": "Poz\u00edci\u00f3k JSON \u00fatvonal",
    "Subject": "T\u00e1rgy",
    "Sent": "Elk\u00fcldve",
    "No logs found": "Nincsenek napl\u00f3k",
    "Critical": "Kritikus",
    "Warning": "Figyelmeztet\u00e9s",
    "Info": "Info",
    "Cancelled": "T\u00f6r\u00f6lve",
    "Archived": "Archiv\u00e1lt",
    "Search...": "Keres\u00e9s...",
    "Confirm": "Meger\u0151s\u00edt\u00e9s",
    "Schedule": "\u00dctemez\u00e9s",
    "No activity recorded": "Nincs aktivit\u00e1s r\u00f6gz\u00edtve",
    "Ops not available": "M\u0171veletek nem el\u00e9rhet\u0151k",
    "No signature": "Nincs al\u00e1\u00edr\u00e1s",
    "Signature accepted": "Al\u00e1\u00edr\u00e1s elfogadva",
    "Cleaned up": "Kitakar\u00edtva",
}

TR_EXTRA = {
    "Calculate a route to see details.": "Detaylar\u0131 g\u00f6rmek i\u00e7in bir rota hesaplay\u0131n.",
    "Add to Dispatch": "Dispatch'e Ekle",
    "Send to Calculator": "Hesap Makinesine G\u00f6nder",
    "Client Name": "M\u00fc\u015fteri Ad\u0131",
    "No saved route ID": "Kaydedilmi\u015f rota ID'si yok",
    "Start Date": "Ba\u015flang\u0131\u00e7 Tarihi",
    "Stop {n}": "Durak {n}",
    "Trip Created": "Seyahat Olu\u015fturuldu",
    "Recommended": "\u00d6nerilen",
    "Fastest": "En H\u0131zl\u0131",
    "Cheapest": "En Ucuz",
    "Safest": "En G\u00fcvenli",
    "Shortest": "En K\u0131sa",
    "Click map to add stop": "Durak eklemek i\u00e7in haritaya t\u0131klay\u0131n",
    "Route loaded": "Rota y\u00fcklendi",
    "Route Options": "Rota Se\u00e7enekleri",
    "Plan multi-stop routes with cost estimation": "Maliyet tahminiyle \u00e7ok durakl\u0131 rotalar planlay\u0131n",
    "Route Planner": "Rota Planlay\u0131c\u0131",
    "Share Route": "Rotay\u0131 Payla\u015f",
    "Share link": "Ba\u011flant\u0131y\u0131 payla\u015f",
    "Copy": "Kopyala",
    "Export File": "Dosyay\u0131 D\u0131\u015fa Aktar",
    "Save & Open Folder": "Kaydet ve Klas\u00f6r\u00fc A\u00e7",
    "Copied!": "Kopyaland\u0131!",
    "Clipboard unavailable": "Pano kullan\u0131lam\u0131yor",
    "Saved: {path}": "Kaydedildi: {path}",
    "Calculate Route": "Rotay\u0131 Hesapla",
    "Distance": "Mesafe",
    "Duration": "S\u00fcre",
    "Recalculate": "Yeniden Hesapla",
    "Archive": "Ar\u015fivle",
    "Export JSON": "JSON D\u0131\u015fa Aktar",
    "Export CSV": "CSV D\u0131\u015fa Aktar",
    "Compare": "Kar\u015f\u0131la\u015ft\u0131r",
    "Loading map...": "Harita y\u00fckleniyor...",
    "Filter by truck": "Kamyona g\u00f6re filtrele",
    "Filter by Truck": "Kamyona G\u00f6re Filtrele",
    "Confirm Archive": "Ar\u015fivlemeyi Onayla",
    "Archive these routes?": "Bu rotalar ar\u015fivlensin mi?",
    "Confirm Delete": "Silmeyi Onayla",
    "Delete these routes?": "Bu rotalar silinsin mi?",
    "Routes exported successfully.": "Rotalar ba\u015far\u0131yla d\u0131\u015fa aktar\u0131ld\u0131.",
    "Routes recalculated successfully.": "Rotalar ba\u015far\u0131yla yeniden hesapland\u0131.",
    "Search routes...": "Rota ara...",
    "Select truck...": "Kamyon se\u00e7...",
    "Review and manage saved routes": "Kaydedilmi\u015f rotalar\u0131 g\u00f6zden ge\u00e7irin ve y\u00f6netin",
    "Route History": "Rota Ge\u00e7mi\u015fi",
    "Active:": "Aktif:",
    "Archived:": "Ar\u015fivlenmi\u015f:",
    "Date:": "Tarih:",
    "Truck:": "Kamyon:",
    "Distance:": "Mesafe:",
    "Duration:": "S\u00fcre:",
    "Fleet Tracking": "Filo Takibi",
    "Tracking Platform": "Takip Platformu",
    "Platform not configured": "Platform yap\u0131land\u0131r\u0131lmam\u0131\u015f",
    "API Token": "API Anahtar\u0131",
    "Server URL": "Sunucu URL'si",
    "Account / Subdomain": "Hesap / Alt Alan Ad\u0131",
    "ID Field": "ID Alan\u0131",
    "Latitude Field": "Enlem Alan\u0131",
    "Longitude Field": "Boylam Alan\u0131",
    "Not Configured": "Yap\u0131land\u0131r\u0131lmam\u0131\u015f",
    "Positions JSON Path": "Pozisyon JSON Yolu",
    "Subject": "Konu",
    "Sent": "G\u00f6nderildi",
    "No logs found": "G\u00fcnl\u00fck bulunamad\u0131",
    "Critical": "Kritik",
    "Warning": "Uyar\u0131",
    "Info": "Bilgi",
    "Cancelled": "\u0130ptal Edildi",
    "Archived": "Ar\u015fivlendi",
    "Search...": "Ara...",
    "Confirm": "Onayla",
    "Schedule": "Program",
    "No activity recorded": "Kaydedilmi\u015f aktivite yok",
    "Ops not available": "Operasyonlar mevcut de\u011fil",
    "No signature": "\u0130mza yok",
    "Signature accepted": "\u0130mza kabul edildi",
    "Cleaned up": "Temizlendi",
}

# Add HU_EXTRA and TR_EXTRA to REMAINING_MAP
for k, v in HU_EXTRA.items():
    if k not in REMAINING_MAP:
        REMAINING_MAP[k] = {"cs": k, "pt": k, "hu": v, "tr": k}
    else:
        REMAINING_MAP[k]["hu"] = v

for k, v in TR_EXTRA.items():
    if k not in REMAINING_MAP:
        REMAINING_MAP[k] = {"cs": k, "pt": k, "hu": k, "tr": v}
    else:
        REMAINING_MAP[k]["tr"] = v

def process_file(lang_code):
    filepath = os.path.join(TRANS_DIR, f"{lang_code}.json")
    data = load_json(filepath)
    flat = flatten(data)
    en = load_json(os.path.join(TRANS_DIR, "en.json"))
    en_flat = flatten(en)
    
    changes = 0
    for k, en_v in en_flat.items():
        if not isinstance(en_v, str) or not en_v.strip():
            continue
        if k not in flat:
            continue
        current_v = flat[k]
        if not isinstance(current_v, str):
            continue
        if current_v != en_v:
            continue  # Already translated
        
        # Check remaining map
        if en_v in REMAINING_MAP and lang_code in REMAINING_MAP[en_v]:
            new_v = REMAINING_MAP[en_v][lang_code]
            if new_v != en_v:
                flat[k] = new_v
                changes += 1
    
    if changes > 0:
        new_data = unflatten(flat)
        save_json(filepath, new_data)
    
    return changes

for lang in ["cs", "pt", "hu", "tr"]:
    changes = process_file(lang)
    print(f"  {lang}.json: {changes} additional translations applied")

# All done
