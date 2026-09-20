from src.transform.macro import transform_world_bank


def test_transform_world_bank_drops_null_values():
    payload = [
        {
            "countryiso3code": "ZAF",
            "country": {"value": "South Africa"},
            "indicator": {"id": "FP.CPI.TOTL.ZG", "value": "Inflation, consumer prices (annual %)"},
            "date": "2025",
            "value": 3.2,
            "unit": "",
            "obs_status": "",
        },
        {
            "countryiso3code": "ZAF",
            "country": {"value": "South Africa"},
            "indicator": {"id": "FP.CPI.TOTL.ZG", "value": "Inflation, consumer prices (annual %)"},
            "date": "2026",
            "value": None,
            "unit": "",
            "obs_status": "",
        },
    ]
    df = transform_world_bank(payload)
    assert len(df) == 1
    assert df.iloc[0]["year"] == 2025
