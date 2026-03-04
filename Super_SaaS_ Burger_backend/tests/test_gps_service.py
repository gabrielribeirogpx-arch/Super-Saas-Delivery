from app.services.gps_service import calculate_distance_km, estimate_eta_seconds


def test_calculate_distance_km_haversine():
    # São Paulo -> Rio de Janeiro ~357km em linha reta
    distance = calculate_distance_km(-23.5505, -46.6333, -22.9068, -43.1729)
    assert 350 <= distance <= 370


def test_estimate_eta_seconds_from_distance():
    assert estimate_eta_seconds(15, avg_speed_kmh=30) == 1800
    assert estimate_eta_seconds(15, avg_speed_kmh=0) == 0
