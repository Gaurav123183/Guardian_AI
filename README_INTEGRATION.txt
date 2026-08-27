GUARDIAN AI - ROUTE FEATURE INTEGRATION

This package is based on the uploaded gps_safety_trial-main feature.

KEEP YOUR MAIN WEBSITE:
    templates/index.html
Use your existing GuardianAI_index_updated.html as templates/index.html.

REPLACE/ADD THESE FILES:
    app.py
    ml_risk_predictor.py
    random_forest_risk_model.pkl
    amravati_safety_data.csv
    important_places.csv
    safety_ml_dataset.csv
    area_risk.csv
    area_risk_1.csv
    dummy_police_stations.csv
    safety_data.csv
    requirements.txt

The new app.py keeps the uploaded feature's OSRM + rule-based + Random Forest route engine and adds compatibility endpoints used by the main Guardian AI landing page:
    GET /api/geocode
    GET /api/current-city
    GET /api/safety-points
    GET /api/routes

Run:
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    python3 app.py

Open:
    http://127.0.0.1:8989

IMPORTANT:
- Do not rename random_forest_risk_model.pkl.
- Keep all CSV files in the same directory as app.py.
- Keep the website file at templates/index.html.
- The main website's /api/routes call is now served by the uploaded route feature.
- OSRM remains the routing engine; no Google Maps/GeoAPI replacement is used.
