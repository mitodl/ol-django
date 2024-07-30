"""Constants for the Payment Gateway."""

MITOL_PAYMENT_GATEWAY_CYBERSOURCE = "CyberSource"

CYBERSOURCE_DECISION_ACCEPT = "ACCEPT"
CYBERSOURCE_DECISION_DECLINE = "DECLINE"
CYBERSOURCE_DECISION_REVIEW = "REVIEW"
CYBERSOURCE_DECISION_ERROR = "ERROR"
CYBERSOURCE_DECISION_CANCEL = "CANCEL"

CYBERSOURCE_CARD_TYPES = {
    "001": "Visa",
    "002": "Mastercard",
    "003": "American Express",
    "004": "Discover",
    "005": "Diners Club",
    "006": "Carte Blanche",
    "007": "JCB",
    "014": "Enroute",
    "021": "JAL",
    "024": "Maestro (UK)",
    "031": "Delta",
    "033": "Visa Electron",
    "034": "Dankort",
    "036": "Carte Bancaires",
    "037": "Carta Si",
    "039": "EAN",
    "040": "UATP",
    "042": "Maestro (Intl)",
    "050": "Hipercard",
    "051": "Aura",
    "054": "Elo",
    "061": "RuPay",
    "062": "China UnionPay",
}

ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
