"""
Second-pass translator: handles the remaining ~400 untranslated values.
Reads the already-partially-translated hr.json and applies the missing translations.
"""
from __future__ import annotations

import json, re, sys

with open('data/translations/en.json', 'r', encoding='utf-8') as f:
    en = json.load(f)
with open('data/translations/hr.json', 'r', encoding='utf-8') as f:
    hr = json.load(f)

ACRONYMS = {'ID', 'KM', 'VIN', 'EUR', 'N/A', 'CSV', 'PDF', 'OCR', 'GPS', 'API',
            'CMR', 'KPI', 'SMTP', 'DSO', 'SLA', 'SOC', 'GDPR', 'CUI', 'VAT',
            'ETA', 'SMS', 'GBP', 'USD', 'RON', 'JSON', 'BOM', 'UTF-8'}

CRO_CHARS = set('čćšžđČĆŠŽĐ')
CRO_WORDS = {'iznos','datum','opis','kategorija','aktivan','model','godina','inspekcija','osiguranje',
             'klijent','dobit','kamion','vozač','bruto','status','izvezi','spremljen','napomene','telefon',
             'limit','stajalište','udaljenost','trajanje','prihod','trošak','ruta','plaća','gorivo',
             'cestarina','marža','ukupno','greška','upozorenje','potvrda','pregled','dodaj','uredi',
             'izbriši','spremi','odustani','poništi','pretraga','vozilo','neto','održavanje','povijest',
             'postavke','jezik','flota','tablica','oznaka','valuta','dnevno','dodatni','planiranje',
             'početka','izračunaj','unesite','analize','stopa','sigurnost','upravljanje','podacima',
             'poslovna','inteligencija','razdoblje','osvježi','mjesečni','prosječna','neplaćeni',
             'aktivne','financijski','učinak','najbolji','mjesec','centar','evolucija','registarska',
             'grafikoni','odaberite','obavezna','neispravna','vrijednosti','brisanje','vrsta',
             'operativno','fakturiranje','e-pošta','prikaži','generiranje','vizualne','prilagođeno',
             'pokušajte','jedinstvene','nepoznata','uspješan','dostupno','povratak','blokirano',
             'istekla','prekoračeni','otkazano','današnji','sažetak','polazi','dolazi','dodijeli',
             'predloženi','vraćeno','ponovljeno','neraspoređene','očišćeno','raspored','planer',
             'pametna','isključene','izračunavanje','metapodaci','očisti','poveznica','kopiraj',
             'mapu','kopirano','međuspremnik','nedostupan','preostalo','zaglavlje','bilješke',
             'dobavljač','izvrsno','dobro','zakazano','predviđanja','zdravlje','ponavljajući',
             'problemi','interval','kilometraža','sljedeći','zastoj','dnevni','prosjek',
             'kalibracije','aktivnost','tahografa','istječe','tijeku','zadnjih','nedavni',
             'prekršaji','istekao','važeći','sati','profakture','upravljajte','porezna',
             'profaktura','uključi','stajališta','održavanje','povijest','postavke'}

def is_croatian(val):
    if not isinstance(val, str) or not val.strip():
        return True
    if CRO_CHARS & set(val):
        return True
    words = val.lower().split()
    for w in words:
        wc = w.strip('.:(),{}[]%')
        if wc in CRO_WORDS or (len(wc) > 3 and any(wc.endswith(s) for s in ['čki','čka','čko','anje','enje','nje','ost','cija','ića','ač','ica','ilo'])):
            return True
    return False

def is_acronym_only(val):
    if not isinstance(val, str) or not val.strip():
        return True
    words = val.split()
    return all(w.strip('.:(),{}[]%#').upper() in ACRONYMS or 
               w.strip('.:(),{}[]%#') in ('', 'L', 'h', 'm', 's', 'km', 'kg', '€', '%', '/', '—', '→', '•')
               for w in words)

# All remaining English→Croatian translations  
HR_REMAINING = {
    'ERP': 'ERP',
    '───────────────────────────────────────────────────────────': '───────────────────────────────────────────────────────────',
    'Total Cost': 'Ukupni trošak',
    '[{type}] {msg}': '[{type}] {msg}',
    'Servis na (KM):': 'Servis na (KM):',
    'Osiguranje/Inspekcija': 'Osiguranje/Inspekcija',
    'L/100km': 'L/100km',
    'Excel': 'Excel',
    '€/km': '€/km',
    'INV-': 'INV-',
    'Bruto/km': 'Bruto/km',
    'Most Profitable Routes': 'Najprofitabilnije rute',
    'Fuel Cost per KM': 'Trošak goriva po KM',
    'Volume & Cost': 'Volumen i trošak',
    'Cost & Maintenance': 'Trošak i održavanje',
    'Cost Breakdown': 'Raščlamba troškova',
    'Top 3': 'Top 3',
    'Cost Per Truck': 'Trošak po kamionu',
    'Fuel Cost Trend': 'Trend troškova goriva',
    'Maintenance Cost': 'Trošak održavanja',
    'Most Frequent': 'Najčešće',
    '#{id} {truck_number} — {client_name} [{created_at}]': '#{id} {truck_number} — {client_name} [{created_at}]',
    'Plan multi-stop routes with cost estimation': 'Planirajte rute s više stajališta s procjenom troškova',
    'Filter by truck': 'Filtriraj po kamionu',
    'Filter by Truck': 'Filtriraj po kamionu',
    'RO12345678': 'RO12345678',
    'J40/123/2023': 'J40/123/2023',
    '07xx xxx xxx': '07xx xxx xxx',
    'contact@firma.ro': 'contact@firma.ro',
    'LIVE': 'UŽIVO',
    '{hours:.1f}h/{max_h}h': '{hours:.1f}h/{max_h}h',
    'Try adjusting your search or filter criteria': 'Pokušajte prilagoditi kriterije pretraživanja ili filtriranja',
    'Import CSV': 'Uvezi CSV',
    'Mihai Popescu': 'Mihai Popescu',
    'Sarah Müller': 'Sarah Müller',
    'John Smith': 'John Smith',
    'CEO, Smith Logistics': 'CEO, Smith Logistics',
    'Col Cost': 'Trošak (stupac)',
    'Filter Label': 'Oznaka filtera',
    'Form Cost': 'Trošak (obrazac)',
    'Filter by Severity': 'Filtriraj po ozbiljnosti',
    'Filter Trip': 'Filtriraj turu',
    'Filter Truck': 'Filtriraj kamion',
    'Filter Type': 'Filtriraj vrstu',
    'Filter...': 'Filter...',
    ' km': ' km',
    '{label}: {value}': '{label}: {value}',
    'OK': 'OK',
    'Cost per Month': 'Trošak mjesečno',
    'Cost per Year': 'Trošak godišnje',
    'Total Cost': 'Ukupni trošak',
    'Cost': 'Trošak',
    '📞': '📞',
    '✉': '✉',
    '<': '<',
    '>': '>',
    'No trips match your filter.': 'Nema tura koje odgovaraju vašem filteru.',
    'Place of Loading': 'Mjesto utovara',
    'Goods Description': 'Opis robe',
    'Gross Weight (kg)': 'Bruto težina (kg)',
    'CMR Number': 'CMR broj',
    'CMR International Consignment Note': 'CMR međunarodni teretni list',
    'Convention on the Contract for the International Carriage of Goods by Road (CMR)': 'Konvencija o ugovoru za međunarodni prijevoz robe cestom (CMR)',
    'Select your role to autofill the form': 'Odaberite svoju ulogu za automatsko popunjavanje obrasca',
    'I am the Consignor (Sender)': 'Ja sam pošiljatelj',
    'I am the Consignee (Receiver)': 'Ja sam primatelj',
    'Parties to the Contract': 'Stranke ugovora',
    'Consignor / Shipper': 'Pošiljatelj / Otpremnik',
    'EXPEDITOR / EXPEDITEUR': 'EXPEDITOR / EXPEDITEUR',
    'Consignee': 'Primatelj',
    'DESTINATAR / CONSIGNATAIRE': 'DESTINATAR / CONSIGNATAIRE',
    'Boxes 1-2': 'Polja 1-2',
    'Route & Attached Documents': 'Ruta i priloženi dokumenti',
    'Boxes 3-5': 'Polja 3-5',
    'LOCUL PREDARII MARFII / LIEU DE PRISE EN CHARGE': 'LOCUL PREDARII MARFII / LIEU DE PRISE EN CHARGE',
    'Locality / Country': 'Mjesto / Država',
    'LOCUL LIVRARII MARFII / LIEU DE LIVRAISON': 'LOCUL LIVRARII MARFII / LIEU DE LIVRAISON',
    'Loading Country': 'Zemlja utovara',
    'Delivery Country': 'Zemlja isporuke',
    'Documents attached': 'Priloženi dokumenti',
    'DOCUMENTE ANEXATE / DOCUMENTS ANNEXES': 'DOCUMENTE ANEXATE / DOCUMENTS ANNEXES',
    'Vehicle & Driver': 'Vozilo i vozač',
    'Boxes 6-7': 'Polja 6-7',
    'Trailer plate': 'Registarska oznaka prikolice',
    'Driver name': 'Ime vozača',
    'Driver license': 'Vozačka dozvola',
    'Cargo Description': 'Opis tereta',
    'Boxes 8-14': 'Polja 8-14',
    '+ Add ADR Entry': '+ Dodaj ADR unos',
    'Boxes 13-17': 'Polja 13-17',
    'Instructions (carriage, customs, insurance)': 'Upute (prijevoz, carina, osiguranje)',
    "INSTRUCTIUNILE EXPEDITORULUI / INSTRUCTIONS DE L'EXPEDITEUR": "INSTRUCTIUNILE EXPEDITORULUI / INSTRUCTIONS DE L'EXPEDITEUR",
    'Carrier reservations and observations': 'Rezervacije i primjedbe prijevoznika',
    'REZERVARILE TRANSPORTATORULUI / RESERVES DU TRANSPORTEUR': 'REZERVARILE TRANSPORTATORULUI / RESERVES DU TRANSPORTEUR',
    'Payment instruction': 'Uputa za plaćanje',
    'MODALITATEA DE PLATA / INSTRUCTION DE PAIEMENT': 'MODALITATEA DE PLATA / INSTRUCTION DE PAIEMENT',
    'Cash on delivery (COD)': 'Plaćanje pouzećem',
    'PLATA LA LIVRARE / REMBOURSEMENT': 'PLATA LA LIVRARE / REMBOURSEMENT',
    'Amount (EUR)': 'Iznos (EUR)',
    'Special agreements': 'Posebni dogovori',
    'INTELEGERI SPECIALE / CONVENTIONS SPECIALES': 'INTELEGERI SPECIALE / CONVENTIONS SPECIALES',
    'DISTANTA / DISTANCE': 'DISTANTA / DISTANCE',
    'Total transport distance': 'Ukupna udaljenost prijevoza',
    'Carrier': 'Prijevoznik',
    'Boxes 18-19': 'Polja 18-19',
    'Carrier (Transporter)': 'Prijevoznik',
    'TRANSPORTATOR / TRANSPORTEUR': 'TRANSPORTATOR / TRANSPORTEUR',
    '+ Add successive carrier': '+ Dodaj uzastopnog prijevoznika',
    'Charges (Box 20)': 'Troškovi (polje 20)',
    'The sender pays / The consignee pays': 'Plaća pošiljatelj / Plaća primatelj',
    'Cost type': 'Vrsta troška',
    'Sender': 'Pošiljatelj',
    'Consignee': 'Primatelj',
    'Issue & Signatures': 'Izdavanje i potpisi',
    'Boxes 21-24': 'Polja 21-24',
    'Established in': 'Sastavljeno u',
    'Place': 'Mjesto',
    'City / Country': 'Grad / Država',
    'Signature — Consignor (Sender)': 'Potpis — Pošiljatelj',
    'Signature — Carrier (Transporter)': 'Potpis — Prijevoznik',
    'Signature — Consignee': 'Potpis — Primatelj',
    'VAT/CUI:': 'PDV/OIB:',
    'EORI:': 'EORI:',
    'Tel:': 'Tel:',
    'Contact:': 'Kontakt:',
    'Email:': 'E-pošta:',
    'Reg No:': 'Reg. br:',
    'Name, address, country': 'Ime, adresa, država',
    'List attached documents': 'Popis priloženih dokumenata',
    'Country': 'Država',
    'Danger': 'Opasnost',
    'Attachments Empty': 'Privitci su prazni',
    'Body:': 'Tijelo:',
    'Browse Title': 'Naslov pregledavanja',
    'Delete this pipeline run and its processed file?': 'Izbrisati ovu izvedbu i njezinu obrađenu datoteku?',
    'Continue to Email': 'Nastavi na e-poštu',
    'Copy path': 'Kopiraj put',
    '🗑 Delete': '🗑 Izbriši',
    'Select a run to view details': 'Odaberite izvedbu za prikaz detalja',
    'Package saved to:\n{path}': 'Paket spremljen u:\n{path}',
    'No documents to package.': 'Nema dokumenata za pakiranje.',
    '📄 Download Combined PDF': '📄 Preuzmi kombinirani PDF',
    '📥 Download': '📥 Preuzmi',
    '📦 Download ZIP': '📦 Preuzmi ZIP',
    'Drop images or PDFs here': 'Ispustite slike ili PDF-ove ovdje',
    'Send Customer Package': 'Pošalji paket klijentu',
    'Email address is not valid.': 'Adresa e-pošte nije važeća.',
    'Please enter a recipient address.': 'Molimo unesite adresu primatelja.',
    'Advanced': 'Napredno',
    'Mode:': 'Način:',
    'Simple': 'Jednostavno',
    'There are no documents to send. Cancel and run the automation first.': 'Nema dokumenata za slanje. Prvo otkažite i pokrenite automatizaciju.',
    'No documents': 'Nema dokumenata',
    'Internal error: package row creation failed': 'Interna greška: stvaranje reda paketa nije uspjelo',
    '(No documents linked to this trip yet)': '(Još nema dokumenata povezanih s ovom turom)',
    'Package for {trip}': 'Paket za {trip}',
    'Prepare Customer Package': 'Pripremi paket za klijenta',
    'Related documents:': 'Povezani dokumenti:',
    'Save document as…': 'Spremi dokument kao...',
    'Search all trips…': 'Pretraži sve ture...',
    'Select a trip to link this document to:': 'Odaberite turu za povezivanje ovog dokumenta:',
    'Send': 'Pošalji',
    'Send Documents': 'Pošalji dokumente',
    'Sending…': 'Slanje...',
    'Skip — Create Package': 'Preskoči — kreiraj paket',
    'Standalone Package': 'Samostalni paket',
    'Subject:': 'Predmet:',
    'Automation': 'Automatizacija',
    'Document Automation': 'Automatizacija dokumenata',
    'To:': 'Za:',
    'Type email address...': 'Upišite adresu e-pošte...',
    'Trip not found': 'Tura nije pronađena',
    'Cannot read input: {}': 'Nije moguće pročitati unos: {}',
    'Database error: {}': 'Greška baze podataka: {}',
    'Processing failed: {}': 'Obrada nije uspjela: {}',
    'OCR failed: {}': 'OCR nije uspio: {}',
    'OCR persistence failed': 'OCR postojanost nije uspjela',
    'Match persistence failed': "Postojanost podudaranja nije uspjela",
    'Grouping failed: {}': 'Grupiranje nije uspjelo: {}',
    'Grouping produced no document': 'Grupiranje nije proizvelo dokument',
    'No trip match — run finished without attachment': 'Nema podudaranja ture — izvedba završena bez privitka',
    'Imported {} ({} bytes)': 'Uvezeno {} ({} bajtova)',
    'Enhanced → {} ({} pages, {} images)': 'Poboljšano → {} ({} stranica, {} slika)',
    'OCR complete: {} chars, confidence={}%, engine={}': 'OCR dovršen: {} znakova, pouzdanost={}%, motor={}',
    'Match: trip #{} confidence={}% ({} candidates)': 'Podudaranje: tura #{} pouzdanost={}% ({} kandidata)',
    'Match required manual selection ({} candidates)': 'Podudaranje zahtijeva ručni odabir ({} kandidata)',
    'Simple mode: processing complete, awaiting user action': 'Jednostavni način: obrada dovršena, čeka se radnja korisnika',
    'Linked document #{} to trip #{}': 'Povezan dokument #{} s turom #{}',
    'Trip #{} — {} ({} → {})': 'Tura #{} — {} ({} → {})',
    'Matching failed: {}': 'Podudaranje nije uspjelo: {}',
    'Scanned — {}': 'Skenirano — {}',
    'Run #{}': 'Izvedba #{}',
    'Status:': 'Status:',
    'Stage:': 'Faza:',
    'Matched trip:': 'Podudarna tura:',
    'Extracted fields:': 'Izdvojena polja:',
    'Top candidates:': 'Najbolji kandidati:',
    'Doc #{}': 'Dok. #{}',
    'Failed to create standalone document. Check that the processed PDF exists on disk.': 'Nije uspjelo stvaranje samostalnog dokumenta. Provjerite postoji li obrađeni PDF na disku.',
    'Failed to build the package. Try again.': 'Nije uspjelo izgraditi paket. Pokušajte ponovno.',
    'Document processed — choose an action below.': 'Dokument obrađen — odaberite radnju ispod.',
    'Optionally select a trip to associate this document with:': 'Opcionalno odaberite turu za povezivanje ovog dokumenta:',
    'Image files (*.png *.jpg *.jpeg *.bmp);;All files (*.*)': 'Slikovne datoteke (*.png *.jpg *.jpeg *.bmp);;Sve datoteke (*.*)',
    'Selected: {}': 'Odabrano: {}',
    'Loaded: {}': 'Učitano: {}',
    'Receipt Generator': 'Generator potvrda',
    'Create professional receipts for payments, reimbursements and expenses': 'Kreirajte profesionalne potvrde za plaćanja, povrate i troškove',
    'Attach Files': 'Priloži datoteke',
    'Select File': 'Odaberi datoteku',
    'Validation Error': 'Greška validacije',
    'Receipt Generated': 'Potvrda generirana',
    'PDF saved to: {path}': 'PDF spremljen u: {path}',
    'No receipt number. Generate first.': 'Nema broja potvrde. Prvo generirajte.',
    'No PDF file found. Generate first.': 'Nema PDF datoteke. Prvo generirajte.',
    'Receipt Duplicated': 'Potvrda duplicirana',
    'Copy created with new number.': 'Kopija kreirana s novim brojem.',
    'Email feature coming soon.': 'Mogućnost e-pošte uskoro dolazi.',
    'No files attached.': 'Nema priloženih datoteka.',
    'Draft name:': 'Naziv nacrta:',
    'Draft "{name}" saved.': 'Nacrt "{name}" spremljen.',
    'No drafts saved yet.': 'Još nema spremljenih nacrta.',
    'RECEIPT TYPE': 'VRSTA POTVRDE',
    'RECEIPT INFORMATION': 'INFORMACIJE O POTVRDI',
    'PARTIES': 'STRANKE',
    'PAYMENT DETAILS': 'DETALJI PLAĆANJA',
    'LOGISTICS': 'LOGISTIKA',
    'PURPOSE': 'SVRHA',
    'FINANCIAL': 'FINANCIJSKI',
    'EMPLOYEE EXPENSES': 'TROŠKOVI ZAPOSLENIKA',
    'ATTACHMENTS': 'PRIVITCI',
    'BRANDING & SIGNATURES': 'BRENDIRANJE I POTPISI',
    'Customer Payment': 'Plaćanje klijenta',
    'Cash Receipt': 'Gotovinska potvrda',
    'Driver Reimbursement': 'Povrat troškova vozaču',
    'Employee Expense Reimbursement': 'Povrat troškova zaposleniku',
    'Fuel Reimbursement': 'Povrat troškova goriva',
    'Toll Reimbursement': 'Povrat troškova cestarina',
    'Miscellaneous Business Expense': 'Razni poslovni troškovi',
    'Refund': 'Povrat novca',
    'Deposit': 'Depozit',
    'Advance Payment': 'Avansno plaćanje',
    'Receipt No.': 'Broj potvrde',
    'Auto-generated': 'Automatski generirano',
    'YYYY-MM-DD': 'GGGG-MM-DD',
    'Payment Date': 'Datum plaćanja',
    'Language': 'Jezik',
    'Received From': 'Primljeno od',
    'Received By': 'Primio',
    'Payment Method': 'Način plaćanja',
    'Reference No.': 'Referentni broj',
    'Transaction ID': 'ID transakcije',
    'Bank Reference': 'Bankovna referenca',
    'Invoice Reference': 'Referenca računa',
    'Related Trip': 'Povezana tura',
    'Trip #': 'Tura #',
    'Pickup Location': 'Lokacija preuzimanja',
    'Delivery Location': 'Lokacija isporuke',
    'Purpose': 'Svrha',
    '0.00': '0,00',
    'Enter the payment amount': 'Unesite iznos plaćanja',
    'VAT Rate (%)': 'Stopa PDV-a (%)',
    'e.g. 19': 'npr. 25',
    'Optional': 'Opcionalno',
    'VAT Amount': 'Iznos PDV-a',
    'Amount in Words': 'Iznos slovima',
    'Auto-calculated': 'Automatski izračunato',
    'Employee Name': 'Ime zaposlenika',
    'Department': 'Odjel',
    'Expense Category': 'Kategorija troška',
    'Accommodation': 'Smještaj',
    'Meals': 'Obroci',
    'Parking': 'Parkiranje',
    'Tolls': 'Cestarina',
    'Company Logo': 'Logotip tvrtke',
    'Path to logo image': 'Put do slike logotipa',
    'Path to signature image': 'Put do slike potpisa',
    'Company Stamp': 'Pečat tvrtke',
    'Path to stamp image': 'Put do slike pečata',
    'Company Signature': 'Potpis tvrtke',
    'Recipient Signature': 'Potpis primatelja',
    'Company Stamp': 'Pečat tvrtke',
    'Generated by Operion': 'Generirano od Operiona',
    'Amount is required and must be positive.': 'Iznos je obavezan i mora biti pozitivan.',
    'Recipient (Received From) is required.': 'Primatelj (Primljeno od) je obavezan.',
    'Receipt number is required.': 'Broj potvrde je obavezan.',
    'Issue date is required.': 'Datum izdavanja je obavezan.',
    'e.g. Bucharest HQ': 'npr. Zagreb',
    'Data exported to: {path}': 'Podaci izvezeni u: {path}',
    'VAT rate must be between 0 and 100.': 'Stopa PDV-a mora biti između 0 i 100.',
    '{field} must be in YYYY-MM-DD format.': '{field} mora biti u formatu GGGG-MM-DD.',
    'QUICK FILL FROM INVOICE': 'BRZO POPUNJAVANJE IZ RAČUNA',
    'Select Invoice': 'Odaberi račun',
    'Select an invoice to auto-fill receipt fields': 'Odaberite račun za automatsko popunjavanje polja potvrde',
    'Attachment Type': 'Vrsta privitka',
    'Receipt Photo': 'Fotografija potvrde',
    'Fuel Receipt': 'Potvrda o gorivu',
    'POD': 'POD',
    'Document': 'Dokument',
    'Image': 'Slika',
    'Will be completed': 'Bit će dovršeno',
    'Enter an amount above': 'Unesite iznos iznad',
    '{speed:.0f} km/h': '{speed:.0f} km/h',
    'This is a test notification from the Operations Engine.': 'Ovo je testna obavijest iz Operacijskog motora.',
    '{value} ms': '{value} ms',
    'SELECT * FROM table LIMIT 100': 'SELECT * FROM table LIMIT 100',
    '············': '············',
    'Route Planning & Optimization': 'Planiranje i optimizacija ruta',
    'Intelligent Route Planning': 'Inteligentno planiranje ruta',
    'Advanced algorithms optimize for time, distance, fuel, and toll costs across Europe.': 'Napredni algoritmi optimiziraju vrijeme, udaljenost, gorivo i troškove cestarina diljem Europe.',
    'Multi-Stop Optimization': 'Optimizacija više stajališta',
    'Plan complex multi-stop routes with up to 50 waypoints and automated sequencing.': 'Planirajte složene rute s do 50 putnih točaka i automatskim sekvenciranjem.',
    'Real-Time Traffic Integration': 'Integracija prometa u stvarnom vremenu',
    'Routes adjust dynamically based on live traffic conditions and road closures.': 'Rute se dinamički prilagođavaju na temelju prometnih uvjeta i zatvaranja cesta.',
    'Fleet Management': 'Upravljanje voznim parkom',
    'Real-Time GPS Tracking': 'GPS praćenje u stvarnom vremenu',
    "Monitor every vehicle's location, speed, and status on an interactive map.": 'Nadzirite lokaciju, brzinu i status svakog vozila na interaktivnoj karti.',
    'Vehicle Maintenance Tracking': 'Praćenje održavanja vozila',
    'Schedule and track maintenance with automated alerts for inspections, insurance, and services.': 'Planirajte i pratite održavanje s automatskim upozorenjima za inspekcije, osiguranje i servise.',
    'Geofencing & Alerts': 'Geofencing i upozorenja',
    'Set geographic boundaries and receive instant notifications when vehicles enter or leave zones.': 'Postavite geografske granice i primajte trenutne obavijesti kada vozila uđu ili izađu iz zona.',
    'Dispatch & Operations': 'Dispečing i operacije',
    'Automated Job Assignment': 'Automatsko dodjeljivanje poslova',
    'Match jobs to the best available drivers and trucks based on location, skills, and compliance.': 'Spojite poslove s najboljim dostupnim vozačima i kamionima na temelju lokacije, vještina i usklađenosti.',
    'Digital Proof of Delivery': 'Digitalni dokaz isporuke',
    'Capture signatures, photos, and timestamps at delivery for complete proof of delivery.': 'Snimite potpise, fotografije i vremenske oznake pri isporuci za potpuni dokaz isporuke.',
    'Real-Time Status Updates': 'Ažuriranja statusa u stvarnom vremenu',
    'Track every job from assignment to completion with live status updates.': 'Pratite svaki posao od dodjele do završetka s ažuriranjima statusa uživo.',
    'Document Management': 'Upravljanje dokumentima',
    'AI-Powered OCR': 'OCR pokretan umjetnom inteligencijom',
    'Scan and digitize invoices, CMRs, receipts, and contracts with AI-powered OCR.': 'Skenirajte i digitalizirajte račune, CMR-ove, potvrde i ugovore OCR-om pokretanim umjetnom inteligencijom.',
    'Digital Archive': 'Digitalni arhiv',
    'Store and search all documents with version history, tags, and full-text search.': 'Pohranite i pretražujte sve dokumente s poviješću verzija, oznakama i pretraživanjem punog teksta.',
    'Automated Invoicing': 'Automatsko fakturiranje',
    'Generate invoices from delivery data automatically and email them to clients.': 'Automatski generirajte račune iz podataka o isporuci i pošaljite ih e-poštom klijentima.',
    'Analytics & Reporting': 'Analitika i izvješćivanje',
    'Custom Dashboards': 'Prilagođene nadzorne ploče',
    'Build personalized views with KPIs, charts, and real-time data.': 'Izgradite personalizirane prikaze s KPI-jevima, grafikonima i podacima u stvarnom vremenu.',
    'KPI Tracking': 'Praćenje KPI-jeva',
    'Monitor key performance indicators including profit per mile, fuel efficiency, and driver performance.': 'Pratite ključne pokazatelje uspješnosti uključujući dobit po milji, učinkovitost goriva i učinak vozača.',
    'Export & Integration': 'Izvoz i integracija',
    'Export reports in multiple formats and integrate with your existing ERP and accounting software.': 'Izvezite izvješća u više formata i integrirajte s vašim postojećim ERP i računovodstvenim softverom.',
    'Driver Profiles': 'Profili vozača',
    'Complete driver database with licenses, medical certificates, contracts, and documents.': 'Potpuna baza podataka vozača s dozvolama, liječničkim potvrdama, ugovorima i dokumentima.',
    'Performance Tracking': 'Praćenje učinka',
    'Monitor driver efficiency, safety scores, tachograph compliance, and driving hours.': 'Pratite učinkovitost vozača, sigurnosne rezultate, usklađenost tahografa i sate vožnje.',
    'Schedule Management': 'Upravljanje rasporedom',
    'Plan driver shifts, manage availability, and track working hours.': 'Planirajte smjene vozača, upravljajte dostupnošću i pratite radno vrijeme.',
    'Today, Operion powers fleets across Europe, helping them plan smarter, dispatch faster, and grow bigger.': 'Danas Operion pokreće vozne parkove diljem Europe, pomažući im pametnije planirati, brže dispečirati i više rasti.',
    'Our Values': 'Naše vrijednosti',
    'The principles that guide every decision we make.': 'Načela koja vode svaku našu odluku.',
    'Customer First': 'Klijent na prvom mjestu',
    'Every feature we build starts with real customer needs and feedback.': 'Svaka značajka koju gradimo počinje sa stvarnim potrebama i povratnim informacijama klijenata.',
    'Reliability': 'Pouzdanost',
    'Your operations depend on our software. We take that responsibility seriously.': 'Vaše operacije ovise o našem softveru. Tu odgovornost shvaćamo ozbiljno.',
    'Innovation': 'Inovacija',
    'We invest heavily in R&D to bring cutting-edge AI and optimization to logistics.': 'Mnogo ulažemo u istraživanje i razvoj kako bismo donijeli vrhunsku umjetnu inteligenciju i optimizaciju u logistiku.',
    'Transparency': 'Transparentnost',
    'Clear pricing, honest communication, and no hidden fees.': 'Jasne cijene, poštena komunikacija i bez skrivenih naknada.',
    'Security': 'Sigurnost',
    'Enterprise-grade encryption, GDPR compliance, and regular security audits.': 'Enkripcija na razini poduzeća, usklađenost s GDPR-om i redovite sigurnosne revizije.',
    'Partnership': 'Partnerstvo',
    "We don't just sell software. We partner with our customers for their success.": 'Ne prodajemo samo softver. Partnerimo s našim klijentima za njihov uspjeh.',
    'Our Team': 'Naš tim',
    'Our team combines decades of experience in logistics, software engineering, and AI.': 'Naš tim kombinira desetljeća iskustva u logistici, softverskom inženjerstvu i umjetnoj inteligenciji.',
    'Sign In — Operion ERP': 'Prijava — Operion ERP',
    'Back to home': 'Natrag na početnu',
    'Operion': 'Operion',
    'Welcome back': 'Dobrodošli natrag',
    'Sign in to your Operion account': 'Prijavite se na svoj Operion račun',
    'you@company.com': 'vi@tvrtka.com',
    'Forgot password?': 'Zaboravili ste lozinku?',
    'Enter your password': 'Unesite vašu lozinku',
    'Hide password': 'Sakrij lozinku',
    'Show password': 'Prikaži lozinku',
    'Signing in…': 'Prijava...',
    'Sign in': 'Prijava',
    "Don't have an account?": 'Nemate račun?',
    'Sign up': 'Registracija',
    'Signed in successfully!': 'Uspješno prijavljeni!',
    'Failed to sign in': 'Prijava nije uspjela',
    'Please enter a valid email': 'Molimo unesite važeću e-poštu',
    'Password is required': 'Lozinka je obavezna',
    'Password must be at most 72 characters': 'Lozinka smije imati najviše 72 znaka',
    'Create Account — Operion ERP': 'Kreiraj račun — Operion ERP',
    'Back to home': 'Natrag na početnu',
    'Operion': 'Operion',
    'Create your account': 'Kreirajte vaš račun',
    'Start your 14-day free trial': 'Započnite 14-dnevno besplatno probno razdoblje',
    'Full Name': 'Puno ime',
    'John Doe': 'Ivan Horvat',
    'Company Name (optional)': 'Naziv tvrtke (opcionalno)',
    'Acme Inc.': 'Tvrtka d.o.o.',
    'At least 8 characters': 'Najmanje 8 znakova',
    'Confirm Password': 'Potvrdite lozinku',
    'Repeat your password': 'Ponovite vašu lozinku',
    'Creating account…': 'Stvaranje računa...',
    'Create account': 'Kreiraj račun',
    'Already have an account?': 'Već imate račun?',
    'Account created successfully!': 'Račun uspješno kreiran!',
    'Failed to create account': 'Stvaranje računa nije uspjelo',
    'Name must be at least 2 characters': 'Ime mora imati najmanje 2 znaka',
    'Password must be at least 8 characters': 'Lozinka mora imati najmanje 8 znakova',
    "Passwords don't match": 'Lozinke se ne podudaraju',
    'Upload & OCR': 'Učitavanje i OCR',
    'Browse...': 'Pretraži...',
    'Upload & Run OCR': 'Učitaj i pokreni OCR',
}

def walk_and_translate(en_obj, hr_obj):
    """Walk both structures and translate identical values."""
    if isinstance(en_obj, dict) and isinstance(hr_obj, dict):
        result = {}
        for k in en_obj:
            if k in hr_obj:
                result[k] = walk_and_translate(en_obj[k], hr_obj[k])
            else:
                result[k] = hr_obj[k] if k in hr_obj else en_obj[k]
        for k in hr_obj:
            if k not in en_obj:
                result[k] = hr_obj[k]
        return result
    elif isinstance(en_list := en_obj, list) and isinstance(hr_list := hr_obj, list):
        result = []
        for i in range(max(len(en_list), len(hr_list))):
            if i < len(en_list) and i < len(hr_list):
                result.append(walk_and_translate(en_list[i], hr_list[i]))
            elif i < len(en_list):
                result.append(en_list[i])
            else:
                result.append(hr_list[i])
        return result
    elif isinstance(en_obj, str) and isinstance(hr_obj, str):
        if en_obj == hr_obj:
            # Check if it needs translation
            if not is_croatian(hr_obj) and not is_acronym_only(hr_obj) and hr_obj.strip():
                tr = HR_REMAINING.get(en_obj)
                if tr:
                    return tr
                # Try to find by case-insensitive key
                for eng, cro in HR_REMAINING.items():
                    if eng.lower() == en_obj.lower():
                        return cro
                # Still untranslated, try TRANSLATIONS from the main script
                return hr_obj  # Keep as-is if no translation found
        return hr_obj
    else:
        return hr_obj

new_hr = walk_and_translate(en, hr)

with open('data/translations/hr.json', 'w', encoding='utf-8') as f:
    json.dump(new_hr, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Validate
with open('data/translations/hr.json', 'r', encoding='utf-8') as f:
    validated = json.load(f)

def count_remaining(en_obj, hr_obj):
    c = 0
    if isinstance(en_obj, dict) and isinstance(hr_obj, dict):
        for k in en_obj:
            if k in hr_obj:
                c += count_remaining(en_obj[k], hr_obj[k])
    elif isinstance(en_obj, list) and isinstance(hr_obj, list):
        for e, h in zip(en_obj, hr_obj):
            c += count_remaining(e, h)
    elif isinstance(en_obj, str) and isinstance(hr_obj, str) and en_obj == hr_obj:
        if not is_croatian(en_obj) and not is_acronym_only(en_obj) and en_obj.strip():
            c += 1
    return c

remaining = count_remaining(en, validated)
print(f'\nRemaining untranslated: {remaining}')
if remaining == 0:
    print('SUCCESS: All values translated!')
else:
    print(f'WARNING: {remaining} values still need translation')
