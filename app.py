from flask import Flask, render_template, jsonify, request
from pathlib import Path
import csv
import math
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import pandas as pd
from datetime import datetime
import random
import requests
import os
import certifi


# ============================================================
# IMPORT ML PREDICTOR
# ============================================================

try:
    from ml_risk_predictor import predict_risk
except ImportError:
    print("ML predictor not found. Using fallback.")
    predict_risk = None


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)
BASE = Path(__file__).resolve().parent


# ============================================================
# API CONFIGURATION
# ============================================================

OSRM_URL = "https://router.project-osrm.org"

NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"

HEADERS = {
    "User-Agent": "GuardianAI/1.0"
}


# ============================================================
# SSL / HTTPS CONFIGURATION
# ============================================================

# Use certifi's trusted CA bundle.
# This fixes:
#
# SSL: CERTIFICATE_VERIFY_FAILED
# unable to get local issuer certificate
#
CERT_VERIFY = certifi.where()


# ============================================================
# SAFETY DATA LOADING
# ============================================================

SAFETY_FILE = "amravati_safety_data.csv"


def load_safety_data():

    try:

        df = pd.read_csv(BASE / SAFETY_FILE)

        required = [
            "latitude",
            "longitude",
            "risk_score"
        ]

        missing = [
            column
            for column in required
            if column not in df.columns
        ]

        if missing:

            print("Safety dataset missing:", missing)

            return create_mock_safety_data()


        df["latitude"] = pd.to_numeric(
            df["latitude"],
            errors="coerce"
        )

        df["longitude"] = pd.to_numeric(
            df["longitude"],
            errors="coerce"
        )

        df["risk_score"] = pd.to_numeric(
            df["risk_score"],
            errors="coerce"
        )


        for col in [
            "crime_risk",
            "lighting_level",
            "crowd_density",
            "traffic_level",
            "police_presence"
        ]:

            if col not in df.columns:

                df[col] = 50.0


        df = df.dropna(
            subset=[
                "latitude",
                "longitude"
            ]
        )


        print(
            "Safety data loaded:",
            len(df),
            "records"
        )

        return df


    except Exception as error:

        print(
            "Safety dataset error:",
            error
        )

        return create_mock_safety_data()


def create_mock_safety_data():

    """
    Create fallback safety data for Amravati.
    """

    mock_data = []


    locations = [

        {
            "name": "Rajapeth Area",
            "lat": 20.929,
            "lon": 77.752,
            "risk": 58,
            "crime": 55,
            "lighting": 60,
            "crowd": 80,
            "traffic": 75,
            "police": 45
        },

        {
            "name": "Gadge Nagar",
            "lat": 20.941,
            "lon": 77.765,
            "risk": 42,
            "crime": 35,
            "lighting": 70,
            "crowd": 55,
            "traffic": 50,
            "police": 60
        },

        {
            "name": "Camp Area",
            "lat": 20.925,
            "lon": 77.755,
            "risk": 55,
            "crime": 48,
            "lighting": 55,
            "crowd": 75,
            "traffic": 70,
            "police": 50
        },

        {
            "name": "Badnera Road",
            "lat": 20.91,
            "lon": 77.735,
            "risk": 64,
            "crime": 62,
            "lighting": 45,
            "crowd": 65,
            "traffic": 85,
            "police": 35
        },

        {
            "name": "University Area",
            "lat": 20.945,
            "lon": 77.77,
            "risk": 32,
            "crime": 25,
            "lighting": 80,
            "crowd": 60,
            "traffic": 45,
            "police": 70
        },

        {
            "name": "Bus Stand",
            "lat": 20.933,
            "lon": 77.7525,
            "risk": 70,
            "crime": 70,
            "lighting": 50,
            "crowd": 95,
            "traffic": 90,
            "police": 40
        },

        {
            "name": "Railway Station",
            "lat": 20.926,
            "lon": 77.758,
            "risk": 66,
            "crime": 65,
            "lighting": 55,
            "crowd": 90,
            "traffic": 85,
            "police": 45
        },

        {
            "name": "Shivaji Nagar",
            "lat": 20.937,
            "lon": 77.76,
            "risk": 38,
            "crime": 30,
            "lighting": 72,
            "crowd": 50,
            "traffic": 45,
            "police": 65
        },

        {
            "name": "Panchwati Square",
            "lat": 20.918,
            "lon": 77.75,
            "risk": 57,
            "crime": 50,
            "lighting": 58,
            "crowd": 78,
            "traffic": 80,
            "police": 48
        },

        {
            "name": "Morshi Road",
            "lat": 20.95,
            "lon": 77.78,
            "risk": 50,
            "crime": 45,
            "lighting": 62,
            "crowd": 65,
            "traffic": 70,
            "police": 55
        }

    ]


    for loc in locations:

        mock_data.append({

            "latitude": loc["lat"],

            "longitude": loc["lon"],

            "location_name": loc["name"],

            "area_name": loc["name"],

            "place_type": "Mixed",

            "risk_score": loc["risk"],

            "risk_level":
                "High"
                if loc["risk"] >= 65
                else
                "Medium"
                if loc["risk"] >= 40
                else
                "Low",

            "crime_risk": loc["crime"],

            "lighting_level": loc["lighting"],

            "crowd_density": loc["crowd"],

            "traffic_level": loc["traffic"],

            "police_presence": loc["police"]

        })


    return pd.DataFrame(mock_data)


safety_data = load_safety_data()


# ============================================================
# MANUAL IMPORTANT PLACES
# ============================================================

MANUAL_POINTS = [

    {
        "name": "Sipna College of Engineering and Technology",
        "type": "education",
        "lat": 20.8809,
        "lon": 77.7474,
        "source": "Institutional published location / coordinate source"
    },

    {
        "name": "Amravati Railway Station",
        "type": "railway_station",
        "lat": 20.93071,
        "lon": 77.75807,
        "source": "OpenStreetMap-derived source"
    },

    {
        "name": "New Amravati Railway Station",
        "type": "railway_station",
        "lat": 20.90304,
        "lon": 77.7329,
        "source": "OpenStreetMap-derived source"
    },

    {
        "name": "Rajapeth Police Station",
        "type": "police_station",
        "lat": 20.923847,
        "lon": 77.754114,
        "source": "Police listing / location directory"
    },

    {
        "name": "Amravati City Kotwali Police Station",
        "type": "police_station",
        "lat": 20.930163,
        "lon": 77.753666,
        "source": "OpenStreetMap-derived source"
    },

    {
        "name": "Nagpuri Gate Police Station",
        "type": "police_station",
        "lat": 20.93634,
        "lon": 77.74445,
        "source": "OpenStreetMap-derived source"
    },

    {
        "name": "Police Station Frezarpura",
        "type": "police_station",
        "lat": 20.9324023,
        "lon": 77.7762455,
        "source": "Location directory / OpenStreetMap-derived listing"
    },

    {
        "name": "Police Head Quarters, Amravati",
        "type": "police_headquarters",
        "lat": 20.9315724,
        "lon": 77.7734955,
        "source": "OpenStreetMap-derived source"
    },

    {
        "name": "Commissioner Of Police Office, Amravati",
        "type": "police_office",
        "lat": 20.9311243,
        "lon": 77.7751887,
        "source": "Location directory"
    },

    {
        "name": "Government College of Engineering Amravati",
        "type": "education",
        "lat": 20.95713,
        "lon": 77.75692,
        "source": "OpenStreetMap-derived source"
    },

    {
        "name": "Government Vidarbha Institute of Science and Humanities",
        "type": "education",
        "lat": 20.95573,
        "lon": 77.75498,
        "source": "OpenStreetMap-derived source"
    },

    {
        "name": "Shri Ambadevi Temple",
        "type": "religious_landmark",
        "lat": 20.92726,
        "lon": 77.74891,
        "source": "OpenStreetMap-derived Mapcarta; Government of Maharashtra confirms temple is in central Amravati"
    },

    {
        "name": "Jawahar Gate",
        "type": "historical_landmark",
        "lat": 20.93192,
        "lon": 77.75006,
        "source": "OpenStreetMap-derived Mapcarta / Wikimedia Commons"
    },

    {
        "name": "Rajkamal Square",
        "type": "commercial_traffic_hub",
        "lat": 20.92867,
        "lon": 77.75265,
        "source": "MPCB Amravati Environmental Study; commercial/traffic hub"
    },

    {
        "name": "Maltekdi",
        "type": "hill_landmark",
        "lat": 20.932762,
        "lon": 77.76915,
        "source": "Published geographic coordinate source; Government of Maharashtra identifies Maltekdi as a hill inside the city"
    },

    {
        "name": "Bamboo Garden Amravati",
        "type": "park_tourist_place",
        "lat": 20.922792,
        "lon": 77.792397,
        "source": "Wikimedia Commons GPS-tagged photograph; current reporting identifies Bamboo Garden as a major city facility"
    },

    {
        "name": "Wadali Talav",
        "type": "waterbody_tourist_place",
        "lat": 20.925,
        "lon": 77.7953,
        "source": "OpenStreetMap-derived Mapcarta; Maharashtra Tourism lists Wadali Talav as a city attraction"
    },

    {
        "name": "Wadali Garden",
        "type": "park_tourist_place",
        "lat": 20.927921,
        "lon": 77.793177,
        "source": "Published latitude/longitude source; structured local business listing"
    },

    {
        "name": "Joshi Market",
        "type": "market_commercial",
        "lat": 20.92961,
        "lon": 77.75312,
        "source": "OpenStreetMap-derived Mapcarta"
    },

    {
        "name": "Satidham Mandir",
        "type": "religious_landmark",
        "lat": 20.92938,
        "lon": 77.75608,
        "source": "OpenStreetMap-derived Mapcarta"
    },

    {
        "name": "Gajanan Maharaj Temple, Dastur Nagar",
        "type": "religious_landmark",
        "lat": 20.9090003,
        "lon": 77.7684206,
        "source": "Published local location directory"
    },

    {
        "name": "Sarafa, Amravati",
        "type": "commercial_area",
        "lat": 20.932142,
        "lon": 77.746864,
        "source": "Published geographic coordinate source"
    },

    {
        "name": "Chhatri Talao Road",
        "type": "tourist_area",
        "lat": 20.9135,
        "lon": 77.762,
        "source": "Published geographic coordinate source; road/area reference"
    }

]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def haversine_km(
    lat1,
    lon1,
    lat2,
    lon2
):

    r = 6371.0

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [
            lat1,
            lon1,
            lat2,
            lon2
        ]
    )

    dlat = lat2 - lat1

    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(dlon / 2) ** 2
    )

    return (
        2
        *
        r
        *
        math.asin(
            math.sqrt(a)
        )
    )


def haversine_m(
    lat1,
    lon1,
    lat2,
    lon2
):

    return (
        haversine_km(
            lat1,
            lon1,
            lat2,
            lon2
        )
        *
        1000
    )


# ============================================================
# HTTPS REQUEST HELPER
# ============================================================

def http_json(
    url,
    params,
    timeout=30
):

    """
    Make a verified HTTPS GET request and return JSON.

    Uses certifi CA bundle so Nominatim requests work
    correctly on macOS/Python installations where the
    system certificate chain is not automatically available.
    """

    try:

        response = requests.get(

            url,

            params=params,

            headers=HEADERS,

            timeout=timeout,

            verify=CERT_VERIFY

        )

        response.raise_for_status()

        return response.json()


    except requests.exceptions.RequestException as error:

        print(
            f"HTTP error: {error}"
        )

        return {}


    except ValueError as error:

        print(
            f"JSON decode error: {error}"
        )

        return {}


# ============================================================
# OSRM ROUTING
# ============================================================

def get_osrm_route(
    start_lat,
    start_lon,
    end_lat,
    end_lon,
    alternatives=True
):

    """
    Get one or more real road routes from OSRM.
    """

    try:

        url = (
            f"{OSRM_URL}"
            f"/route/v1/driving/"
            f"{start_lon},{start_lat};"
            f"{end_lon},{end_lat}"
        )


        params = {

            "alternatives":
                "true"
                if alternatives
                else
                "false",

            "steps": "false",

            "overview": "full",

            "geometries": "geojson"

        }


        response = requests.get(

            url,

            params=params,

            timeout=30,

            headers=HEADERS,

            verify=CERT_VERIFY

        )


        if response.status_code == 200:

            data = response.json()


            if (
                data.get("code") == "Ok"
                and data.get("routes")
            ):

                return data


        print(
            "OSRM route request failed:",
            response.status_code
        )


    except Exception as error:

        print(
            f"OSRM error: {error}"
        )


    return None


# ============================================================
# OSRM WAYPOINT ROUTE
# ============================================================

def get_osrm_waypoint_route(points):

    """
    Route through real road-network waypoints.
    Used only to fill route alternatives.
    """

    try:

        coordinate_string = ";".join(

            f"{lon},{lat}"

            for lat, lon in points

        )


        url = (
            f"{OSRM_URL}"
            f"/route/v1/driving/"
            f"{coordinate_string}"
        )


        params = {

            "alternatives": "false",

            "steps": "false",

            "overview": "full",

            "geometries": "geojson"

        }


        response = requests.get(

            url,

            params=params,

            timeout=30,

            headers=HEADERS,

            verify=CERT_VERIFY

        )


        if response.status_code != 200:

            return None


        data = response.json()


        if (
            data.get("code") == "Ok"
            and data.get("routes")
        ):

            return data["routes"][0]


    except Exception as error:

        print(
            f"OSRM waypoint error: {error}"
        )


    return None


# ============================================================
# ROUTE SIGNATURE
# ============================================================

def route_signature(geometry):

    coords = (
        geometry.get("coordinates", [])
        if geometry
        else []
    )


    if not coords:

        return None


    sample = coords[
        ::max(
            1,
            len(coords) // 12
        )
    ][:12]


    return tuple(

        (
            round(c[0], 4),
            round(c[1], 4)
        )

        for c in sample
        if len(c) >= 2

    )


# ============================================================
# GENERATE ACCURATE ROUTES
# ============================================================

def generate_accurate_routes(
    start_lat,
    start_lon,
    end_lat,
    end_lon
):

    """
    Return up to four connected routes.

    All routes are based on the real OSRM road network.

    If OSRM returns fewer than four alternatives,
    additional connected road routes are generated
    using OSRM waypoints.

    No fake straight lines are drawn.
    """

    dist_km = haversine_km(

        start_lat,
        start_lon,

        end_lat,
        end_lon

    )


    if dist_km < 0.05:

        return []


    routes = []

    seen = set()


    # ========================================================
    # 1. OSRM NATIVE ALTERNATIVES
    # ========================================================

    osrm_data = get_osrm_route(

        start_lat,
        start_lon,

        end_lat,
        end_lon,

        alternatives=True

    )


    if osrm_data:

        for i, route in enumerate(
            osrm_data.get(
                "routes",
                []
            )
        ):

            geometry = route.get(
                "geometry",
                {}
            )


            sig = route_signature(
                geometry
            )


            if not sig or sig in seen:

                continue


            seen.add(sig)


            distance = float(
                route.get(
                    "distance",
                    dist_km * 1000
                )
            )


            duration = float(
                route.get(
                    "duration",
                    distance / 1000
                    * 3.5
                    * 60
                )
            )


            routes.append({

                "id":
                    len(routes) + 1,

                "geometry":
                    geometry,

                "distance":
                    distance,

                "duration":
                    duration,

                "name":
                    "Safest Route"
                    if len(routes) == 0
                    else
                    f"Route {len(routes) + 1}",

                "is_safest":
                    len(routes) == 0,

                "safety_boost":
                    max(
                        0,
                        12 - len(routes) * 3
                    ),

                "source":
                    "OSRM"

            })


            if len(routes) >= 4:

                break


    # ========================================================
    # 2. CONNECTED WAYPOINT ALTERNATIVES
    # ========================================================

    if len(routes) < 4:

        dlat = (
            end_lat
            - start_lat
        )

        dlon = (
            end_lon
            - start_lon
        )


        length = max(

            math.hypot(
                dlat,
                dlon
            ),

            0.0001

        )


        perp_lat = (
            -dlon
            / length
        )

        perp_lon = (
            dlat
            / length
        )


        offset = min(

            0.018,

            max(
                0.004,
                dist_km * 0.0018
            )

        )


        candidate_fractions = [
            0.35,
            0.50,
            0.65
        ]


        candidate_signs = [
            1,
            -1,
            1
        ]


        candidates = []


        for frac, sign in zip(
            candidate_fractions,
            candidate_signs
        ):

            mid_lat = (

                start_lat
                +
                dlat * frac
                +
                perp_lat
                * offset
                * sign

            )


            mid_lon = (

                start_lon
                +
                dlon * frac
                +
                perp_lon
                * offset
                * sign

            )


            candidates.append(
                (
                    mid_lat,
                    mid_lon
                )
            )


        # Additional opposite-side candidate
        if (
            dist_km >= 3
            and len(candidates) < 4
        ):

            candidates.append(

                (

                    start_lat
                    +
                    dlat * 0.55
                    -
                    perp_lat * offset,

                    start_lon
                    +
                    dlon * 0.55
                    -
                    perp_lon * offset

                )

            )


        for waypoint in candidates:

            if len(routes) >= 4:

                break


            route = get_osrm_waypoint_route(

                [

                    (
                        start_lat,
                        start_lon
                    ),

                    waypoint,

                    (
                        end_lat,
                        end_lon
                    )

                ]

            )


            if not route:

                continue


            geometry = route.get(
                "geometry",
                {}
            )


            sig = route_signature(
                geometry
            )


            if not sig or sig in seen:

                continue


            seen.add(sig)


            distance = float(
                route.get(
                    "distance",
                    dist_km * 1000
                )
            )


            duration = float(
                route.get(
                    "duration",
                    distance / 1000
                    * 3.5
                    * 60
                )
            )


            routes.append({

                "id":
                    len(routes) + 1,

                "geometry":
                    geometry,

                "distance":
                    distance,

                "duration":
                    duration,

                "name":
                    "Safest Route"
                    if not routes
                    else
                    f"Route {len(routes) + 1}",

                "is_safest":
                    not routes,

                "safety_boost":
                    max(
                        0,
                        10 - len(routes) * 2
                    ),

                "source":
                    "OSRM waypoint alternative"

            })


    if not routes:

        print(
            "OSRM returned no usable road routes"
        )

        return []


    return routes[:4]


# ============================================================
# CALCULATE ROUTE RISK
# ============================================================

def calculate_route_risk(
    route_geometry,
    safety_boost=0
):

    """
    Calculate route risk using safety data.
    """

    if safety_data.empty:

        base_risk = random.uniform(
            30,
            60
        )


        return {

            "route_risk":
                max(
                    0,
                    min(
                        100,
                        base_risk
                        - safety_boost
                    )
                ),

            "safety_score":
                max(
                    0,
                    min(
                        100,
                        100
                        - base_risk
                        + safety_boost
                    )
                ),

            "risk_points":
                []

        }


    coordinates = route_geometry.get(
        "coordinates",
        []
    )


    if not coordinates:

        return {

            "route_risk": 50,

            "safety_score": 50,

            "risk_points": []

        }


    risk_points = []


    for _, row in safety_data.iterrows():

        try:

            risk_lat = float(
                row["latitude"]
            )

            risk_lon = float(
                row["longitude"]
            )

        except:

            continue


        min_dist = float("inf")


        for coord in coordinates:

            if len(coord) < 2:

                continue


            route_lon = coord[0]

            route_lat = coord[1]


            dist = haversine_km(

                route_lat,
                route_lon,

                risk_lat,
                risk_lon

            )


            if dist < min_dist:

                min_dist = dist


        if min_dist > 0.8:

            continue


        def normalize(v):

            try:

                return max(

                    0.0,

                    min(
                        100.0,
                        float(v)
                    )

                )

            except:

                return 50.0


        crime_risk = normalize(
            row.get(
                "crime_risk",
                50
            )
        )


        lighting_level = normalize(
            row.get(
                "lighting_level",
                50
            )
        )


        crowd_density = normalize(
            row.get(
                "crowd_density",
                50
            )
        )


        traffic_level = normalize(
            row.get(
                "traffic_level",
                50
            )
        )


        police_presence = normalize(
            row.get(
                "police_presence",
                50
            )
        )


        existing_risk = normalize(
            row.get(
                "risk_score",
                50
            )
        )


        lighting_risk = (
            100.0
            - lighting_level
        )


        police_risk = (
            100.0
            - police_presence
        )


        point_risk = (

            crime_risk * 0.30

            +

            lighting_risk * 0.20

            +

            crowd_density * 0.15

            +

            traffic_level * 0.10

            +

            police_risk * 0.15

            +

            existing_risk * 0.10

        )


        point_risk = max(

            0.0,

            min(
                100.0,
                point_risk
            )

        )


        if min_dist <= 0.1:

            weight = 1.0

        elif min_dist <= 0.3:

            weight = 0.7

        elif min_dist <= 0.5:

            weight = 0.3

        else:

            weight = 0.0


        risk_points.append({

            "location_name":
                str(
                    row.get(
                        "location_name",
                        "Risk area"
                    )
                ),

            "latitude":
                risk_lat,

            "longitude":
                risk_lon,

            "distance_km":
                round(
                    min_dist,
                    3
                ),

            "risk_score":
                round(
                    existing_risk,
                    2
                ),

            "crime_risk":
                round(
                    crime_risk,
                    2
                ),

            "lighting_level":
                round(
                    lighting_level,
                    2
                ),

            "crowd_density":
                round(
                    crowd_density,
                    2
                ),

            "traffic_level":
                round(
                    traffic_level,
                    2
                ),

            "police_presence":
                round(
                    police_presence,
                    2
                ),

            "risk_level":
                str(
                    row.get(
                        "risk_level",
                        "Medium"
                    )
                ),

            "weight":
                weight,

            "weighted_risk":
                round(
                    point_risk * weight,
                    2
                )

        })


    total_weighted = sum(

        p.get(
            "weighted_risk",
            0
        )

        for p in risk_points

    )


    total_weight = sum(

        p.get(
            "weight",
            0
        )

        for p in risk_points

    )


    avg_risk = (

        total_weighted
        /
        total_weight

        if total_weight > 0

        else
        50.0

    )


    avg_risk = max(

        0,

        min(
            100,
            avg_risk
        )

    )


    avg_risk = max(

        0,

        min(
            100,
            avg_risk
            - safety_boost
        )

    )


    density_factor = (

        1
        -
        math.exp(
            -len(risk_points)
            /
            60.0
        )

    )


    density_risk = (
        density_factor
        *
        100
    )


    route_risk = (

        avg_risk * 0.70

        +

        density_risk * 0.30

    )


    route_risk = max(

        0,

        min(
            100,
            route_risk
        )

    )


    safety_score = max(

        0,

        min(
            100,
            100 - route_risk
        )

    )


    return {

        "route_risk":
            round(
                route_risk,
                2
            ),

        "safety_score":
            round(
                safety_score,
                2
            ),

        "risk_points":
            risk_points

    }


# ============================================================
# RISK LEVEL
# ============================================================

def get_risk_level(score):

    if score is None:

        return "Unknown"


    score = float(score)


    if score >= 65:

        return "High Risk"


    if score >= 40:

        return "Moderate"


    if score >= 20:

        return "Low"


    return "Very Safe"


# ============================================================
# FINAL RISK
# ============================================================

def calculate_final_risk(
    existing_risk,
    ml_risk,
    risk_point_count
):

    existing_risk = float(
        existing_risk
    )


    if int(risk_point_count) == 0:

        return {

            "final_risk_score":
                existing_risk,

            "final_risk_level":
                get_risk_level(
                    existing_risk
                ),

            "risk_source":
                "existing_algorithm"

        }


    if ml_risk is None:

        return {

            "final_risk_score":
                round(
                    existing_risk,
                    2
                ),

            "final_risk_level":
                get_risk_level(
                    existing_risk
                ),

            "risk_source":
                "existing_algorithm"

        }


    ml_risk = float(
        ml_risk
    )


    final_score = (

        0.4 * existing_risk

        +

        0.6 * ml_risk

    )


    final_score = max(

        0.0,

        min(
            100.0,
            final_score
        )

    )


    return {

        "final_risk_score":
            round(
                final_score,
                2
            ),

        "final_risk_level":
            get_risk_level(
                final_score
            ),

        "risk_source":
            "combined_rule_ml"

    }


# ============================================================
# CLASSIFY MANUAL POINT
# ============================================================

def classify(point):

    t = str(
        point.get(
            "type",
            ""
        )
    ).lower()


    text = (

        str(
            point.get(
                "name",
                ""
            )
        )

        +

        " "

        +

        t

    ).lower()


    if (
        "police" in t
        or
        "police" in text
    ):

        return "police"


    if (
        "hospital" in t
        or
        "clinic" in text
    ):

        return "hospital"


    if any(

        x in text

        for x in [
            "crime",
            "incident",
            "robbery",
            "theft",
            "assault"
        ]

    ):

        return "crime"


    if any(

        x in text

        for x in [
            "market",
            "commercial",
            "traffic"
        ]

    ):

        return "traffic"


    return "place"


# ============================================================
# MANUAL POINTS NEAR ROUTE
# ============================================================

def points_near_route(
    coordinates,
    radius_m=400
):

    points = []


    for p in MANUAL_POINTS:

        lat = p["lat"]

        lon = p["lon"]


        if not coordinates:

            continue


        min_dist = min(

            haversine_m(

                lat,
                lon,

                coord[1],
                coord[0]

            )

            for coord in coordinates[:20]

            if len(coord) >= 2

        )


        if min_dist <= radius_m:

            q = dict(p)


            q["category"] = classify(
                p
            )


            q["distance_m"] = round(
                min_dist
            )


            points.append(q)


    return points


# ============================================================
# ROUTE SAFETY
# ============================================================

def route_safety(coordinates):

    nearby = points_near_route(

        coordinates,

        450

    )


    crime = [

        p

        for p in nearby

        if p.get(
            "category"
        ) == "crime"

    ]


    traffic = [

        p

        for p in nearby

        if p.get(
            "category"
        ) == "traffic"

    ]


    police = [

        p

        for p in nearby

        if p.get(
            "category"
        ) == "police"

    ]


    hospitals = [

        p

        for p in nearby

        if p.get(
            "category"
        ) == "hospital"

    ]


    risk_penalty = min(

        70,

        len(crime) * 12
        +
        len(traffic) * 5

    )


    support_bonus = min(

        15,

        len(police) * 3
        +
        len(hospitals) * 2

    )


    score = round(

        max(

            0,

            min(

                100,

                100
                -
                risk_penalty
                +
                support_bonus

            )

        ),

        1

    )


    return {

        "score":
            score,

        "crime_points":
            len(crime),

        "police_nearby":
            len(police),

        "hospitals_nearby":
            len(hospitals)

    }


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# GEOCODE
# ============================================================

@app.route("/api/geocode")
def geocode():

    text = request.args.get(
        "text",
        ""
    ).strip()


    if len(text) < 2:

        return jsonify({
            "results": []
        })


    try:

        data = http_json(

            NOMINATIM_SEARCH,

            {

                "q":
                    text,

                "format":
                    "jsonv2",

                "limit":
                    8,

                "addressdetails":
                    1

            },

            timeout=15

        )


        if not data:

            return jsonify({
                "results": []
            })


        results = []


        for x in data:

            if (
                x.get("lat")
                and
                x.get("lon")
            ):

                results.append({

                    "formatted":
                        x.get(
                            "display_name",
                            "Unknown place"
                        ),

                    "lat":
                        float(
                            x["lat"]
                        ),

                    "lon":
                        float(
                            x["lon"]
                        ),

                    "type":
                        x.get(
                            "type",
                            "place"
                        )

                })


        return jsonify({
            "results": results
        })


    except Exception as exc:

        print(
            f"Geocode error: {exc}"
        )

        return jsonify({

            "error":
                str(exc),

            "results":
                []

        }), 502


# ============================================================
# CURRENT CITY
# ============================================================

@app.route("/api/current-city")
def current_city():

    lat = request.args.get(
        "lat"
    )

    lon = request.args.get(
        "lon"
    )


    if not lat or not lon:

        return jsonify({

            "city":
                "Current Location"

        })


    try:

        data = http_json(

            NOMINATIM_REVERSE,

            {

                "lat":
                    lat,

                "lon":
                    lon,

                "format":
                    "jsonv2",

                "zoom":
                    18

            },

            timeout=15

        )


        address = data.get(
            "address",
            {}
        )


        city = (

            address.get(
                "city"
            )

            or

            address.get(
                "town"
            )

            or

            address.get(
                "village"
            )

            or

            "Current Location"

        )


        return jsonify({

            "city":
                city,

            "formatted":
                data.get(
                    "display_name",
                    city
                )

        })


    except Exception as exc:

        print(
            f"Current city error: {exc}"
        )


        return jsonify({

            "city":
                "Current Location"

        }), 200


# ============================================================
# SAFETY DATA API
# ============================================================

@app.route("/api/safety-data")
def safety_data_api():

    if safety_data.empty:

        return jsonify({

            "success":
                False,

            "data":
                []

        })


    records = []


    for _, row in safety_data.iterrows():

        records.append({

            "latitude":
                float(
                    row["latitude"]
                ),

            "longitude":
                float(
                    row["longitude"]
                ),

            "location_name":
                str(
                    row.get(
                        "location_name",
                        ""
                    )
                ),

            "area_name":
                str(
                    row.get(
                        "area_name",
                        ""
                    )
                ),

            "place_type":
                str(
                    row.get(
                        "place_type",
                        ""
                    )
                ),

            "risk_score":
                float(
                    row.get(
                        "risk_score",
                        0
                    )
                ),

            "risk_level":
                str(
                    row.get(
                        "risk_level",
                        "Unknown"
                    )
                ),

            "crime_risk":
                float(
                    row.get(
                        "crime_risk",
                        0
                    )
                ),

            "lighting_level":
                float(
                    row.get(
                        "lighting_level",
                        0
                    )
                ),

            "crowd_density":
                float(
                    row.get(
                        "crowd_density",
                        0
                    )
                ),

            "traffic_level":
                float(
                    row.get(
                        "traffic_level",
                        0
                    )
                ),

            "police_presence":
                float(
                    row.get(
                        "police_presence",
                        0
                    )
                )

        })


    return jsonify({

        "success":
            True,

        "data":
            records

    })


# ============================================================
# DESTINATIONS
# ============================================================

@app.route("/api/destinations")
def destinations_api():

    """
    Manually curated important places.

    These are used for:
    - Destination suggestions
    - Search shortcuts
    - Manual location matching

    They are NOT permanent map markers.
    """

    places = []


    for p in MANUAL_POINTS:

        places.append({

            "name":
                p["name"],

            "latitude":
                p["lat"],

            "longitude":
                p["lon"],

            "type":
                p["type"],

            "source":
                p.get(
                    "source",
                    "Guardian AI curated location"
                )

        })


    return jsonify({

        "success":
            True,

        "data":
            places

    })


# ============================================================
# ROUTES API
# ============================================================

@app.route("/api/routes")
def get_routes():

    try:

        start_lat = float(
            request.args[
                "start_lat"
            ]
        )

        start_lon = float(
            request.args[
                "start_lon"
            ]
        )

        end_lat = float(
            request.args[
                "end_lat"
            ]
        )

        end_lon = float(
            request.args[
                "end_lon"
            ]
        )


    except (
        KeyError,
        ValueError
    ):

        return jsonify({

            "error":
                "Valid coordinates required"

        }), 400


    # ========================================================
    # GENERATE REAL ROAD ROUTES
    # ========================================================

    route_variants = generate_accurate_routes(

        start_lat,
        start_lon,

        end_lat,
        end_lon

    )


    if not route_variants:

        return jsonify({

            "error":
                "Could not generate routes"

        }), 400


    routes = []


    for variant in route_variants:

        geometry = variant[
            "geometry"
        ]


        safety_boost = variant.get(

            "safety_boost",

            0

        )


        # ====================================================
        # ROUTE RISK
        # ====================================================

        risk_data = calculate_route_risk(

            geometry,

            safety_boost

        )


        risk_points = risk_data.get(

            "risk_points",

            []

        )


        # ====================================================
        # NEARBY MANUAL SAFETY
        # ====================================================

        safety_info = route_safety(

            geometry.get(
                "coordinates",
                []
            )

        )


        # ====================================================
        # ML PREDICTION
        # ====================================================

        ml_risk_score = None

        ml_risk_level = None


        if (
            predict_risk
            and
            risk_points
        ):

            try:

                def safe_avg(
                    points,
                    field
                ):

                    vals = [

                        float(
                            p.get(
                                field,
                                50
                            )
                        )

                        for p in points

                        if p.get(
                            field
                        ) is not None

                    ]


                    return (

                        sum(vals)
                        /
                        len(vals)

                        if vals

                        else
                        50

                    )


                crime_risk = safe_avg(

                    risk_points,

                    "crime_risk"

                )


                lighting_level = safe_avg(

                    risk_points,

                    "lighting_level"

                )


                crowd_density = safe_avg(

                    risk_points,

                    "crowd_density"

                )


                traffic_level = safe_avg(

                    risk_points,

                    "traffic_level"

                )


                police_presence = safe_avg(

                    risk_points,

                    "police_presence"

                )


                current_time = datetime.now()


                ml_result = predict_risk(

                    crime_risk=
                        crime_risk,

                    lighting_level=
                        lighting_level,

                    crowd_density=
                        crowd_density,

                    traffic_level=
                        traffic_level,

                    police_presence=
                        police_presence,

                    hour=
                        current_time.hour,

                    day_of_week=
                        current_time.strftime(
                            "%A"
                        )

                )


                ml_risk_score = ml_result.get(

                    "predicted_risk_score"

                )


                ml_risk_level = ml_result.get(

                    "predicted_risk_level"

                )


            except Exception as e:

                print(
                    f"ML error: {e}"
                )


        # ====================================================
        # FINAL RISK
        # ====================================================

        final_risk = calculate_final_risk(

            existing_risk=
                risk_data[
                    "route_risk"
                ],

            ml_risk=
                ml_risk_score,

            risk_point_count=
                len(risk_points)

        )


        # ====================================================
        # COMBINED SAFETY
        # ====================================================

        combined_safety = (

            risk_data[
                "safety_score"
            ]

            +

            safety_info.get(
                "score",
                50
            )

        ) / 2


        # ====================================================
        # ROUTE DATA
        # ====================================================

        route_data = {

            "id":
                variant["id"],

            "distance":
                variant["distance"],

            "duration":
                variant["duration"],

            "geometry":
                geometry,


            "safety": {

                "score":
                    round(
                        combined_safety,
                        1
                    ),

                "crime_risk":
                    round(

                        sum(

                            [
                                p.get(
                                    "crime_risk",
                                    50
                                )

                                for p in risk_points

                            ]

                        )

                        /

                        max(
                            1,
                            len(risk_points)
                        ),

                        1

                    )
                    if risk_points
                    else
                    50,


                "lighting_level":
                    round(

                        sum(

                            [
                                p.get(
                                    "lighting_level",
                                    50
                                )

                                for p in risk_points

                            ]

                        )

                        /

                        max(
                            1,
                            len(risk_points)
                        ),

                        1

                    )
                    if risk_points
                    else
                    50,


                "crowd_density":
                    round(

                        sum(

                            [
                                p.get(
                                    "crowd_density",
                                    50
                                )

                                for p in risk_points

                            ]

                        )

                        /

                        max(
                            1,
                            len(risk_points)
                        ),

                        1

                    )
                    if risk_points
                    else
                    50,


                "traffic_level":
                    round(

                        sum(

                            [
                                p.get(
                                    "traffic_level",
                                    50
                                )

                                for p in risk_points

                            ]

                        )

                        /

                        max(
                            1,
                            len(risk_points)
                        ),

                        1

                    )
                    if risk_points
                    else
                    50,


                "police_presence":
                    round(

                        sum(

                            [
                                p.get(
                                    "police_presence",
                                    50
                                )

                                for p in risk_points

                            ]

                        )

                        /

                        max(
                            1,
                            len(risk_points)
                        ),

                        1

                    )
                    if risk_points
                    else
                    50,


                "crime_points":
                    safety_info.get(
                        "crime_points",
                        0
                    ),

                "police_nearby":
                    safety_info.get(
                        "police_nearby",
                        0
                    ),

                "hospitals_nearby":
                    safety_info.get(
                        "hospitals_nearby",
                        0
                    )

            },


            "safety_score":
                round(
                    combined_safety,
                    1
                ),


            "route_risk":
                risk_data[
                    "route_risk"
                ],


            "risk_points":
                risk_points,


            "ml_risk_score":
                ml_risk_score,


            "ml_risk_level":
                ml_risk_level,


            "final_risk_score":
                final_risk[
                    "final_risk_score"
                ],


            "final_risk_level":
                final_risk[
                    "final_risk_level"
                ],


            "risk_source":
                final_risk[
                    "risk_source"
                ],


            "is_safest":
                variant.get(
                    "is_safest",
                    False
                ),


            "name":
                variant.get(
                    "name",
                    f"Route {variant['id']}"
                ),


            "source":
                variant.get(
                    "source",
                    "Guardian AI"
                )

        }


        routes.append(
            route_data
        )


    # ========================================================
    # BUILD SMALL MAP RISK POINT SET
    # ========================================================

    map_points = {}


    for route in routes:

        for point in route.get(
            "risk_points",
            []
        ):

            key = (

                round(
                    float(
                        point["latitude"]
                    ),
                    4
                ),

                round(
                    float(
                        point["longitude"]
                    ),
                    4
                )

            )


            existing = map_points.get(
                key
            )


            if (

                existing is None

                or

                float(
                    point.get(
                        "risk_score",
                        0
                    )
                )

                >

                float(
                    existing.get(
                        "risk_score",
                        0
                    )
                )

            ):

                map_points[key] = point


    map_risk_points = sorted(

        map_points.values(),

        key=lambda p: (

            float(
                p.get(
                    "risk_score",
                    0
                )
            ),

            -

            float(
                p.get(
                    "distance_km",
                    99
                )
            )

        ),

        reverse=True

    )[:8]


    # ========================================================
    # SORT ROUTES BY SAFETY
    # ========================================================

    routes.sort(

        key=lambda r:
            r["safety_score"],

        reverse=True

    )


    # ========================================================
    # REASSIGN IDs
    # ========================================================

    for idx, route in enumerate(
        routes
    ):

        route["id"] = idx + 1

        route["is_safest"] = (
            idx == 0
        )

        route["name"] = (

            "Safest Route"

            if idx == 0

            else

            f"Route {idx + 1}"

        )


    return jsonify({

        "routes":
            routes,

        "safest_route_id":
            routes[0]["id"]
            if routes
            else
            None,

        "map_risk_points":
            map_risk_points,

        "source":
            "Guardian AI Route Engine"

    })


# ============================================================
# LOCATION SEARCH
# ============================================================

@app.route(
    "/api/search-location",
    methods=["GET"]
)
def search_location():

    query = request.args.get(
        "q",
        ""
    ).strip()


    if not query:

        return jsonify({

            "success":
                False,

            "message":
                "Location search is required"

        }), 400


    # ========================================================
    # 1. SEARCH MANUAL IMPORTANT PLACES FIRST
    # ========================================================

    q = " ".join(
        query.lower().split()
    )


    search_tokens = [

        token

        for token in q.split()

        if token not in {

            "amravati",
            "maharashtra",
            "india"

        }

        and len(token) > 1

    ]


    manual_matches = []


    for p in MANUAL_POINTS:

        haystack = " ".join([

            str(
                p.get(
                    "name",
                    ""
                )
            ),

            str(
                p.get(
                    "type",
                    ""
                )
            )

        ]).lower()


        if (

            q in haystack

            or

            (
                search_tokens
                and
                all(
                    token in haystack
                    for token in search_tokens
                )
            )

        ):

            manual_matches.append({

                "name":
                    p["name"],

                "latitude":
                    float(
                        p["lat"]
                    ),

                "longitude":
                    float(
                        p["lon"]
                    ),

                "type":
                    p["type"],

                "source":
                    p.get(
                        "source",
                        "Guardian AI curated location"
                    )

            })


    # ========================================================
    # 2. NOMINATIM SEARCH
    # ========================================================

    try:

        data = http_json(

            NOMINATIM_SEARCH,

            {

                "q":
                    query,

                "format":
                    "jsonv2",

                "limit":
                    5,

                "addressdetails":
                    1

            },

            timeout=15

        )


    except Exception as error:

        print(
            f"Location search error: {error}"
        )

        data = []


    locations = list(
        manual_matches
    )


    seen = {

        (
            round(
                x["latitude"],
                6
            ),

            round(
                x["longitude"],
                6
            )

        )

        for x in locations

    }


    for result in data or []:

        if (

            result.get("lat")

            and

            result.get("lon")

        ):

            item = {

                "name":
                    result.get(
                        "display_name",
                        query
                    ),

                "latitude":
                    float(
                        result["lat"]
                    ),

                "longitude":
                    float(
                        result["lon"]
                    ),

                "type":
                    result.get(
                        "type",
                        "place"
                    ),

                "source":
                    "nominatim"

            }


            key = (

                round(
                    item["latitude"],
                    6
                ),

                round(
                    item["longitude"],
                    6
                )

            )


            if key not in seen:

                locations.append(
                    item
                )

                seen.add(key)


    if not locations:

        return jsonify({

            "success":
                False,

            "message":
                f'No locations found for "{query}"'

        }), 404


    return jsonify({

        "success":
            True,

        "locations":
            locations[:10]

    })


# ============================================================
# BLUETOOTH EMERGENCY FORWARD
# ============================================================

@app.route(
    "/api/emergency/bluetooth-forward",
    methods=["POST"]
)
def bluetooth_forward():

    payload = (
        request.get_json(
            silent=True
        )
        or
        {}
    )


    print(
        "\n========== GUARDIAN AI BLUETOOTH SOS =========="
    )


    print(
        json.dumps(
            payload,
            indent=2,
            default=str
        )
    )


    print(
        "================================================\n"
    )


    return jsonify({

        "success":
            True,

        "message":
            "Guardian AI received the Bluetooth emergency.",

        "message_id":
            payload.get(
                "message_id"
            )

    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    app.run(

        debug=True,

        host="127.0.0.1",

        port=5000

    )