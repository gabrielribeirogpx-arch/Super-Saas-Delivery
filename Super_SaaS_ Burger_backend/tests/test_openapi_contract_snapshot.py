from scripts.check_openapi_contracts import _critical_paths


def test_critical_paths_only_include_components_referenced_by_critical_routes():
    spec = {
        "paths": {
            "/api/orders": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/OrderResponse"}
                                }
                            }
                        }
                    }
                }
            },
            "/api/admin/tenant/public-settings/cover-upload": {
                "post": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/CoverUploadResponse"}
                                }
                            }
                        }
                    }
                }
            },
        },
        "components": {
            "schemas": {
                "OrderResponse": {
                    "type": "object",
                    "properties": {
                        "payment": {"$ref": "#/components/schemas/PaymentStatus"}
                    },
                },
                "PaymentStatus": {"type": "string"},
                "CoverUploadResponse": {"type": "object"},
            }
        },
    }

    snapshot = _critical_paths(spec)

    assert "/api/orders" in snapshot["paths"]
    assert "/api/admin/tenant/public-settings/cover-upload" not in snapshot["paths"]
    assert snapshot["components"]["schemas"] == {
        "OrderResponse": {
            "type": "object",
            "properties": {
                "payment": {"$ref": "#/components/schemas/PaymentStatus"}
            },
        },
        "PaymentStatus": {"type": "string"},
    }


def test_critical_paths_include_security_schemes_used_by_critical_routes():
    spec = {
        "paths": {
            "/api/inventory/items": {
                "get": {"security": [{"BearerAuth": []}]}
            }
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {"type": "http", "scheme": "bearer"},
                "ApiKeyAuth": {"type": "apiKey", "name": "x-api-key", "in": "header"},
            }
        },
    }

    snapshot = _critical_paths(spec)

    assert snapshot["components"] == {
        "securitySchemes": {
            "BearerAuth": {"type": "http", "scheme": "bearer"}
        }
    }
