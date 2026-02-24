# Synonyme für Status- und Reasoncodes
# Wird in backend/analyzer.py verwendet, um den LLM-Prompt zu generieren.

STATUS_SYNONYMS = [
    "Carrier Event code",
    "Event code",
    "Event",
    "Ereignis",
    "Status",
    "Statuscode",
    "Main code",
    "Scanart",
    "Scan-Art",
    "Shipment Event",
    "Container Event",
    "LSP Statuscode",
    "SE",
    "Sendungsereignis",
    "Scannung",
    "EDIFACT Shipment Event",
    "EDIFACT Container Event"
]

REASON_SYNONYMS_CLASSIC = [
    "additional code",
    "Zusatzcode",
    "reason",
    "error code",
    "substatus",
    "qualifier",
    "reason code"
]

REASON_SYNONYMS_CONTEXT = [
    "Zusatz",
    "Zusatzinfo",
    "Zusatztext",
    "Info",
    "Bemerkung",
    "Detail",
    "Beschreibung (sofern als zusätzliche Qualifizierung zum Status verwendet)"
]

REASON_SYNONYMS_COLUMNS = [
    "codes",
    "codelist",
    "code",
    "Zusatzcodes",
    "Code (bei Scans)",
    "Remarks/Comment/Details"
]

# Normalization map for carrier status descriptions.
# Applied before embedding and BM25 scoring to unify abbreviations,
# multilingual variants, and domain jargon into consistent terms.
CONTENT_NORMALIZATION = {
    # DE abbreviations
    "lkw": "truck",
    "empf.": "empfänger",
    "zust.": "zustellung",
    "abh.": "abholung",
    "sendg.": "sendung",
    "lfg.": "lieferung",
    # Facility synonyms → unified term
    "depot": "facility",
    "terminal": "facility",
    "lager": "facility",
    "hub": "facility",
    "sortierzentrum": "facility",
    # Common carrier jargon
    "avis": "notification",
    "aviso": "notification",
}
