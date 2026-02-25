# Format: (Code, short, long)
# Updated with bilingual descriptions (EN/DE) and keywords for better semantic matching.

CODES = [
   ("ARR", "Arrival / Ankunft",
     "Arrival of the shipment at a facility, depot, or destination terminal. "
     "Ankunft der Sendung im Depot, Terminal oder Standort. "
     "Keywords: arrival scan, arrived, facility, sorting center, eingetroffen, ankunft, lager, eingangsscan, ziel-paketzentrum, depoteingang."),

    ("BCF", "Booking confirmation / Buchungsbestätigung",
     "The shipment booking with the carrier has been confirmed. "
     "Die Buchung wurde vom Transportdienstleister bestätigt. "
     "Keywords: booking confirmed, accepted, shipment booked, buchungsbestätigung, auftrag angenommen, bestätigt, reservierung ok."),

    ("BCK", "Booking / Buchung",
     "The shipment has been booked or transport requested, but not yet confirmed. "
     "Transportauftrag angelegt oder Buchung angefragt. "
     "Keywords: booking created, shipment booked, pickup booked, buchung, auftragserteilung, transportauftrag, angemeldet."),

    ("CAS", "Consignee absence / Empfänger nicht angetroffen",
     "Delivery attempt failed because recipient was not available. "
     "Zustellversuch erfolglos, da Empfänger nicht angetroffen wurde. "
     "Keywords: consignee absent, not at home, card left, closed, recipient not available, failed attempt, "
     "nobody present, absent, delivery attempt failed, no one home, not available, attempted delivery, "
     "zustellhindernis, empfänger nicht da, benachrichtigt, benachrichtigungskarte, firma geschlossen, niemand angetroffen."),

    ("CND", "Delivery cancelled / Storniert",
     "The delivery or shipment has been cancelled. "
     "Die Sendung oder Zustellung wurde storniert. "
     "Keywords: cancelled, shipment cancelled, order cancelled, storno, storniert, auftrag storniert, abbruch, annulliert."),

    ("CUS", "Customs handling / Zollabwicklung",
     "The shipment is under customs processing or inspection. "
     "Sendung befindet sich in der Zollabfertigung oder Beschau. "
     "Keywords: in customs, clearance, held by customs, inspection, zoll, verzollung, zollbeschau, zollfreigabe ausstehend, importverzollung."),

    ("DAM", "Damage / Beschädigung",
     "Damage to the shipment or packaging reported. "
     "Sendung oder Verpackung ist beschädigt. "
     "Keywords: damaged, broken, carton damaged, wet, beschädigt, bruch, beschädigung, karton defekt, nass, inhalt beschädigt, havarie."),

    ("DEL", "Delay / Verzögerung",
     "The shipment is delayed (transit, delivery, or processing). "
     "Verzögerung im Transportablauf oder bei der Zustellung. "
     "Keywords: delay, late, weather delay, operational delay, verzögerung, verspätung, stau, wetterbedingt, lieferverzug, später als geplant."),

    ("DEP", "Departed / Abfahrt",
     "The shipment has departed from a facility, hub, or terminal. "
     "Sendung hat den Standort, das Hub oder Terminal verlassen (Ausgang). "
     "Keywords: departed, left, outbound, forwarded, ausgang, abfahrt, verlassen, warenausgang, weitergeleitet, abgang."),

    ("ERR", "Error / Fehler",
     "General error in processing or data. "
     "Allgemeiner Fehler bei der Verarbeitung oder in den Daten. "
     "Keywords: error, status error, interface error, unknown event, exception, shipment exception, "
     "processing error, system error, data error, invalid event, unhandled status, technical issue, "
     "fehler, störung, verarbeitungsfehler, schnittstellenfehler, ungültiger status."),

    ("ETA", "Estimated time / Avisierung",
     "Expected arrival or delivery date provided. "
     "Voraussichtliches Zustelldatum oder Ankunftszeit aktualisiert (Avis). "
     "Keywords: expected delivery, eta, scheduled, delivery date, avis, avisierung, geplante zustellung, zustellfenster, termin."),

    ("FER", "Fatal error / Kritischer Fehler",
     "Critical unrecoverable error requiring manual intervention. "
     "Kritischer Fehler, der manuelles Eingreifen erfordert. "
     "Keywords: fatal error, hard error, unrecoverable, interface failure, systemfehler, schwerwiegender fehler, abbruch, manuelle klärung."),

    ("GIS", "Goods issue / Warenausgang",
     "Shipment has left the shipper's stock (posted as goods issue). "
     "Warenausgang beim Versender gebucht. "
     "Keywords: goods issue, dispatched from warehouse, stock reduced, warenausgang, versendet, lager verlassen, übergabe an spediteur."),

    ("HDO", "Hand over / Übergabe an DL",
     "Handed over to carrier or parcel shop. "
     "Physische Übergabe an den Transportdienstleister oder Paketshop. "
     "Keywords: handed over, dropped off, carrier receipt, übergabe, eingeliefert, paketshop, einlieferung, an fahrer übergeben."),

    ("HIN", "HUB in / Hub Eingang",
     "Arrival at carrier hub or sorting center. "
     "Eingang im Umschlaglager (Hub) oder Sortierzentrum. "
     "Keywords: hub in, arrival at hub, sorting center, inbound scan, arrived at facility, received at hub, "
     "arrived at terminal, received at sorting center, facility arrival, depot arrival, inbound at hub, "
     "hub eingang, sortierung, umschlagspunkt, eingang depot."),

    ("HOU", "HUB out / Hub Ausgang",
     "Departure from carrier hub or sorting center. "
     "Ausgang aus dem Umschlaglager (Hub) oder Sortierzentrum. "
     "Keywords: hub out, departed hub, left sorting center, outbound scan, hub ausgang, sortierzentrum verlassen, weiterleitung, hauptlauf."),

    ("HUB", "HUB Handling / Umschlag",
     "Processing at hub or sorting center. "
     "Bearbeitung oder Umschlag im Hub/Sortierzentrum. "
     "Keywords: processed at hub, sorting, cross-dock, umschlag, sortierung, hub prozess, lagerdurchlauf, bearbeitung."),

    ("INF", "Info / Information",
     "General info update without physical status change. "
     "Allgemeine Information zur Sendung ohne Statusänderung. "
     "Keywords: info, update, label created, data received, information, datenupdate, auftragsdaten, hinweis."),

    ("IOD", "Delivered / Zugestellt",
     "Shipment successfully delivered to consignee. "
     "Sendung erfolgreich zugestellt. "
     "Keywords: delivered, pod, signed by, left at door, proof of delivery, consignee signed, "
     "delivered to recipient, delivery confirmed, received by, delivery complete, successfully delivered, "
     "zugestellt, empfangen, unterschrift, abstellgenehmigung, abgestellt, erfolgreiche zustellung."),

    ("ITR", "In transit / Unterwegs",
     "Shipment is in transit between facilities. "
     "Sendung ist unterwegs (im Hauptlauf/Transport). "
     "Keywords: in transit, on the way, en route, linehaul, unterwegs, transport, auf dem weg, fahrt, lkw, transit."),

    ("MDA", "Missing data / Fehlende Daten",
     "Missing or incomplete shipment data. "
     "Fehlende oder unvollständige Auftragsdaten. "
     "Keywords: missing data, incomplete address, mandatory field, daten fehlen, unvollständig, adresse fehlt, klärung daten."),

    ("MIS", "Missing Parts / Fehlmenge",
     "Part of shipment or package missing. "
     "Teil der Sendung oder Paket fehlt (Fehlmenge). "
     "Keywords: package missing, short shipment, item not found, colli missing, fehlmenge, paket fehlt, verlust, unterdeckung, nicht vollzählig."),

    ("MPW", "Missing paperwork / Fehlende Papiere",
     "Missing documents (invoice, customs). "
     "Fehlende Dokumente (Rechnung, Zollpapiere). "
     "Keywords: missing invoice, no customs documents, paperwork, papiere fehlen, dokumente fehlen, rechnung fehlt, lieferschein fehlt."),

    ("OFD", "Out for Delivery / In Zustellung",
     "On vehicle for final delivery to recipient. "
     "Sendung befindet sich im Zustellfahrzeug zur Auslieferung. "
     "Keywords: out for delivery, on vehicle, with courier, in zustellung, rollkarte, fahrzeug beladen, auf tour, in auslieferung."),

    ("PAK", "Packed / Verpackt",
     "Shipment packed or repacked. "
     "Sendung wurde verpackt oder umgepackt. "
     "Keywords: packed, repacked, packing complete, verpackt, kommissioniert, packstück erstellt, umgepackt."),

    ("PDL", "Partial Delivery / Teilzustellung",
     "Only part of the shipment delivered. "
     "Nur ein Teil der Sendung wurde zugestellt. "
     "Keywords: partial delivery, incomplete delivery, part delivered, teilzustellung, teillieferung, rest folgt, teilweiser empfang."),

    ("PUP", "Picked Up / Abgeholt",
     "Collected from shipper or pickup location. "
     "Sendung wurde beim Versender oder Abholort abgeholt. "
     "Keywords: picked up, collected, driver pickup, abgeholt, abholung, abholscan, ware übernommen."),

    ("REF", "Refused / Annahme verweigert",
     "Recipient refused shipment. "
     "Empfänger hat die Annahme der Sendung verweigert. "
     "Keywords: refused, rejected, declined, annahme verweigert, verweigerung, annahmeverweigerung, zurückgewiesen."),

    ("RET", "Returned / Retoure",
     "Shipment returned to shipper. "
     "Sendung wird an den Absender zurückgeschickt. "
     "Keywords: returned to sender, rts, return, back to origin, retoure, rücksendung, rücklieferung, zurück an absender."),

    ("UTD", "Unable to deliver / Unzustellbar",
     "Delivery failed, not delivered. "
     "Zustellung nicht möglich (allgemein). "
     "Keywords: unable to deliver, delivery failed, no access, unzustellbar, nicht möglich, zustellabbruch, hindernis."),

    ("WAD", "Wrong Address / Falsche Adresse",
     "Incorrect or incomplete address. "
     "Adresse falsch, unvollständig oder unbekannt. "
     "Keywords: wrong address, insufficient address, unknown recipient, address not found, adresse falsch, empfänger unbekannt, adressfehler, unzustellbar."),

    ("WRN", "Warning / Warnung",
     "Warning or potential issue. "
     "Warnung oder potenzielles Problem. "
     "Keywords: warning, hold, clarification, delay risk, unable to collect, pickup failed, "
     "collection refused, capacity exceeded, attention required, action needed, review required, "
     "warnung, klärung, hinweis, achtung, prüfung."),
]
