"""Constants for the Payment Gateway."""

ISO_8601_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

MITOL_PAYMENT_GATEWAY_NONE = "None"
MITOL_PAYMENT_GATEWAY_CYBERSOURCE = "CyberSource"
MITOL_PAYMENT_GATEWAY_STRIPE = "Stripe"

CART_ITEM_INLINE = "inline"
CART_ITEM_DEFINED = "defined"
CART_ITEM_UNKNOWN = "unknown"

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

STRIPE_PAYMENT_STATUS_PAID = "paid"
STRIPE_PAYMENT_STATUS_NPR = "no_payment_required"
STRIPE_PAYMENT_STATUS_UNPAID = "unpaid"

STRIPE_CHECKOUT_SESSION_STATUS_COMPLETE = "complete"
STRIPE_CHECKOUT_SESSION_STATUS_EXPIRED = "expired"
STRIPE_CHECKOUT_SESSION_STATUS_OPEN = "open"

STRIPE_REFUND_REASON_DUPLICATE = "duplicate"
STRIPE_REFUND_REASON_FRAUD = "fradulent"
STRIPE_REFUND_REASON_CUSTOMER_REQUEST = "requested_by_customer"
STRIPE_REFUND_REASONS = [
    STRIPE_REFUND_REASON_DUPLICATE,
    STRIPE_REFUND_REASON_FRAUD,
    STRIPE_REFUND_REASON_CUSTOMER_REQUEST,
]
