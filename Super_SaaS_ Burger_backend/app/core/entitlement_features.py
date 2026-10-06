"""Stable internal feature codes, independent of providers and plan names."""
NUMERIC_FEATURES = ("orders_monthly", "admin_users", "delivery_users")
BOOLEAN_FEATURES = ("tracking", "whatsapp", "inventory", "coupons", "loyalty", "custom_domain", "advanced_reports")
FEATURE_CODES = frozenset(NUMERIC_FEATURES + BOOLEAN_FEATURES)
