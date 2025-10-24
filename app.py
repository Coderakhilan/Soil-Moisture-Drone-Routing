from flask import Flask, render_template, request, Response
import math, random
from dataclasses import dataclass, asdict
from typing import List, Tuple
import pandas as pd
import folium

app = Flask(__name__)

# -------------------------
# Config
# -------------------------
random.seed(42)
DRY_THRESHOLD = 30.0  # % below which irrigation needed

# -------------------------
# Helpers
# -------------------------
def km_to_deg_lat(km: float) -> float:
    return km / 111.0

def km_to_deg_lon(km: float, lat: float) -> float:
    return km / (111.0 * max(0.1, math.cos(math.radians(lat))))

def sample_point_in_disc(lat0: float, lon0: float, radius_km: float):
    r = radius_km * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi
    dlat = km_to_deg_lat(r) * math.sin(theta)
    dlon = km_to_deg_lon(r, lat0) * math.cos(theta)
    return lat0 + dlat, lon0 + dlon

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return 2*R*math.asin(math.sqrt(a))

def total_path_length_km(points: List[Tuple[float,float]]):
    return sum(haversine(points[i][0],points[i][1],points[i+1][0],points[i+1][1])
               for i in range(len(points)-1)) if len(points)>1 else 0.0

def nearest_neighbor_route(coords: List[Tuple[float,float]]):
    n = len(coords)
    unvisited = set(range(1,n))
    route = [0]
    current = 0
    while unvisited:
        next_node = min(unvisited, key=lambda j: haversine(coords[current][0], coords[current][1],
                                                           coords[j][0], coords[j][1]))
        route.append(next_node)
        unvisited.remove(next_node)
        current = next_node
    route.append(0)
    return route

def two_opt(route: List[int], coords: List[Tuple[float,float]], max_iters: int=200):
    best = route[:]
    best_len = total_path_length_km([coords[i] for i in best])
    improved = True
    iters = 0
    while improved and iters<max_iters:
        improved=False
        iters+=1
        for i in range(1,len(best)-2):
            for k in range(i+1,len(best)-1):
                new_route = best[:i] + best[i:k+1][::-1] + best[k+1:]
                new_len = total_path_length_km([coords[j] for j in new_route])
                if new_len + 1e-9 < best_len:
                    best, best_len, improved = new_route, new_len, True
    return best

@dataclass
class Sensor:
    id: str
    lat: float
    lon: float
    moisture: float

def random_sensors(n, lat, lon, radius):
    return [Sensor(f"SENSOR_{i+1}", *sample_point_in_disc(lat, lon, radius), random.uniform(0,100))
            for i in range(n)]

# -------------------------
# Simulation
# -------------------------
def run_simulation(center_lat=12.969, center_lon=79.159, radius_km=1.0, n_sensors=30):
    DEPOT = {"id":"DRONE_BASE","lat":center_lat,"lon":center_lon}
    sensors = random_sensors(n_sensors, center_lat, center_lon, radius_km)

    dry = [s for s in sensors if s.moisture < DRY_THRESHOLD]
    if len(dry)<3 and len(sensors)>=3:
        dry = sorted(sensors, key=lambda s: s.moisture)[:3]

    coords = [(DEPOT["lat"],DEPOT["lon"])] + [(s.lat,s.lon) for s in dry]
    route_idx = nearest_neighbor_route(coords)
    route_idx = two_opt(route_idx, coords)

    # CSVs in memory
    sensors_df = pd.DataFrame([asdict(s) for s in sensors])
    dry_df = pd.DataFrame([asdict(s) for s in dry])
    route_order = ["DRONE_BASE" if i==0 else dry[i-1].id for i in route_idx]
    route_coords = [coords[i] for i in route_idx]
    route_df = pd.DataFrame({
        "stop_order": list(range(len(route_idx))),
        "node": route_order,
        "lat": [lat for lat,lon in route_coords],
        "lon": [lon for lat,lon in route_coords]
    })

    # Folium maps as HTML strings
    m_all = folium.Map(location=[DEPOT["lat"],DEPOT["lon"]], zoom_start=15)
    folium.Marker([DEPOT["lat"],DEPOT["lon"]], popup="DRONE BASE", icon=folium.Icon(color="blue")).add_to(m_all)
    for s in sensors:
        color = "red" if s.moisture<DRY_THRESHOLD else "orange" if s.moisture<60 else "green"
        folium.Marker([s.lat,s.lon], popup=f"{s.id}: {s.moisture:.1f}%", icon=folium.Icon(color=color)).add_to(m_all)

    m_dry = folium.Map(location=[DEPOT["lat"],DEPOT["lon"]], zoom_start=15)
    folium.Marker([DEPOT["lat"],DEPOT["lon"]], popup="DRONE BASE", icon=folium.Icon(color="blue")).add_to(m_dry)
    for s in dry:
        folium.Marker([s.lat,s.lon], popup=f"{s.id}: {s.moisture:.1f}% (needs irrigation)", icon=folium.Icon(color="red")).add_to(m_dry)
    folium.PolyLine(route_coords, color="blue", weight=4, opacity=0.85).add_to(m_dry)

    return {
        "summary": {
            "n_sensors": len(sensors),
            "dry_count": len(dry),
            "nn_distance": round(total_path_length_km([coords[i] for i in nearest_neighbor_route(coords)]),2),
            "opt_distance": round(total_path_length_km([coords[i] for i in route_idx]),2)
        },
        "maps": {
            "all_sensors": m_all._repr_html_(),
            "dry_route": m_dry._repr_html_()
        },
        "csvs": {
            "all_sensors": sensors_df.to_csv(index=False),
            "dry_sensors": dry_df.to_csv(index=False),
            "route": route_df.to_csv(index=False)
        }
    }

# -------------------------
# Routes
# -------------------------
@app.route("/", methods=["GET"])
def home():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run():
    center_lat = float(request.form.get("center_lat"))
    center_lon = float(request.form.get("center_lon"))
    radius_km = float(request.form.get("radius_km"))
    n_sensors = int(request.form.get("n_sensors"))

    data = run_simulation(center_lat, center_lon, radius_km, n_sensors)
    return render_template("index.html",
                           summary=data["summary"],
                           map_all=data["maps"]["all_sensors"],
                           map_dry=data["maps"]["dry_route"])
                           
# Optional: CSV download route
@app.route("/download/<csv_type>")
def download(csv_type):
    data = run_simulation()
    if csv_type=="all":
        csv_str = data["csvs"]["all_sensors"]
        filename = "all_sensors.csv"
    elif csv_type=="dry":
        csv_str = data["csvs"]["dry_sensors"]
        filename = "dry_sensors.csv"
    elif csv_type=="route":
        csv_str = data["csvs"]["route"]
        filename = "drone_route.csv"
    else:
        return "Invalid type", 404
    return Response(csv_str, mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename={filename}"})
