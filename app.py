from flask import Flask, render_template, request
import math, random, threading, time
from dataclasses import dataclass, asdict
from typing import List, Tuple
import pandas as pd
import folium
import paho.mqtt.client as mqtt
import os

# ------------------------- CONFIG -------------------------
random.seed(42)
DRY_THRESHOLD = 30.0
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
SENSOR_UPDATE_INTERVAL = 3  # seconds
SENSOR_COUNT_DEFAULT = 10
RADIUS_DEFAULT = 1.0
CENTER_DEFAULT = (12.969, 79.159)  # VIT Vellore

# ------------------------- DATA CLASS -------------------------
@dataclass
class Sensor:
    id: str
    lat: float
    lon: float
    moisture: float

# Global list of sensors and their latest values
sensors: List[Sensor] = []

# ------------------------- MQTT -------------------------
client = mqtt.Client()

def mqtt_publish(sensor: Sensor):
    topic = f"farm/{sensor.id}/moisture"
    client.publish(topic, sensor.moisture)

def mqtt_loop():
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    while True:
        for s in sensors:
            # simulate moisture change
            s.moisture = max(0, min(100, s.moisture + random.uniform(-5, 3)))
            mqtt_publish(s)
        time.sleep(SENSOR_UPDATE_INTERVAL)

# ------------------------- HELPERS -------------------------
def km_to_deg_lat(km): return km / 111.0
def km_to_deg_lon(km, lat): return km / (111.0 * max(0.1, math.cos(math.radians(lat))))
def sample_point_in_disc(lat0, lon0, radius_km):
    r = radius_km * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi
    dlat = km_to_deg_lat(r) * math.sin(theta)
    dlon = km_to_deg_lon(r, lat0) * math.cos(theta)
    return lat0 + dlat, lon0 + dlon
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = (math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) *
         math.cos(math.radians(lat2)) * math.sin(dlon/2)**2)
    return 2*R*math.asin(math.sqrt(a))
def total_path_length_km(points): 
    return sum(haversine(points[i][0],points[i][1],points[i+1][0],points[i+1][1])
               for i in range(len(points)-1)) if len(points)>1 else 0

def nearest_neighbor_route(coords):
    n = len(coords)
    unvisited = set(range(1,n))
    route = [0]; current = 0
    while unvisited:
        next_node = min(unvisited, key=lambda j: haversine(coords[current][0], coords[current][1], coords[j][0], coords[j][1]))
        route.append(next_node); unvisited.remove(next_node); current = next_node
    route.append(0)
    return route

def two_opt(route, coords, max_iters=200):
    best = route[:]; best_len = total_path_length_km([coords[i] for i in best])
    improved = True; iters=0
    while improved and iters<max_iters:
        improved=False; iters+=1
        for i in range(1,len(best)-2):
            for k in range(i+1,len(best)-1):
                new_route = best[:i]+best[i:k+1][::-1]+best[k+1:]
                new_len = total_path_length_km([coords[j] for j in new_route])
                if new_len+1e-9 < best_len: best, best_len, improved = new_route, new_len, True
    return best

def random_sensors(n, center_lat, center_lon, radius_km):
    return [Sensor(id=f"SENSOR_{i+1}", lat=sample_point_in_disc(center_lat, center_lon, radius_km)[0],
                   lon=sample_point_in_disc(center_lat, center_lon, radius_km)[1],
                   moisture=random.uniform(0,100)) for i in range(n)]

# ------------------------- SIMULATION -------------------------
def run_simulation(center_lat, center_lon, radius_km, n_sensors):
    global sensors
    DEPOT = {"id":"DRONE_BASE","lat":center_lat,"lon":center_lon}
    sensors = random_sensors(n_sensors, center_lat, center_lon, radius_km)
    dry = [s for s in sensors if s.moisture<DRY_THRESHOLD]
    if len(dry)<3 and len(sensors)>=3: dry = sorted(sensors, key=lambda s: s.moisture)[:3]
    coords = [(DEPOT["lat"],DEPOT["lon"])] + [(s.lat,s.lon) for s in dry]
    route_idx = nearest_neighbor_route(coords)
    route_idx = two_opt(route_idx, coords, max_iters=200)
    
    # Folium maps
    m1 = folium.Map(location=[DEPOT["lat"],DEPOT["lon"]], zoom_start=15)
    folium.Marker([DEPOT["lat"],DEPOT["lon"]], popup="DRONE BASE", icon=folium.Icon(color="blue")).add_to(m1)
    for s in sensors:
        color = "red" if s.moisture<DRY_THRESHOLD else "orange" if s.moisture<60 else "green"
        folium.Marker([s.lat,s.lon], popup=f"{s.id}: {s.moisture:.1f}%", icon=folium.Icon(color=color)).add_to(m1)
    
    m2 = folium.Map(location=[DEPOT["lat"],DEPOT["lon"]], zoom_start=15)
    folium.Marker([DEPOT["lat"],DEPOT["lon"]], popup="DRONE BASE", icon=folium.Icon(color="blue")).add_to(m2)
    for s in dry:
        folium.Marker([s.lat,s.lon], popup=f"{s.id}: {s.moisture:.1f}% (needs irrigation)", icon=folium.Icon(color="red")).add_to(m2)
    route_coords = [coords[i] for i in route_idx]
    folium.PolyLine(route_coords, color="blue", weight=4, opacity=0.85).add_to(m2)
    
    # Save maps in memory as HTML strings
    return m1._repr_html_(), m2._repr_html_(), len(sensors), len(dry), total_path_length_km([coords[i] for i in nearest_neighbor_route(coords)]), total_path_length_km([coords[i] for i in route_idx])

# ------------------------- FLASK -------------------------
app = Flask(__name__)

@app.route("/", methods=["GET","POST"])
def index():
    summary = None
    map_all, map_dry = None, None
    if request.method=="POST":
        center_lat = float(request.form.get("center_lat"))
        center_lon = float(request.form.get("center_lon"))
        radius_km = float(request.form.get("radius_km"))
        n_sensors = int(request.form.get("n_sensors"))
        map_all, map_dry, n_total, n_dry, nn_dist, opt_dist = run_simulation(center_lat, center_lon, radius_km, n_sensors)
        summary = {"n_sensors":n_total,"dry_count":n_dry,"nn_distance":round(nn_dist,3),"opt_distance":round(opt_dist,3)}
    return render_template("index.html", summary=summary, map_all=map_all, map_dry=map_dry)

# ------------------------- RUN -------------------------
if __name__=="__main__":
    threading.Thread(target=mqtt_loop, daemon=True).start()
    app.run(debug=True)
