from flask import Flask, render_template, request
import math, random, threading, time
from dataclasses import dataclass
from typing import List
import folium
import paho.mqtt.client as mqtt

# ------------------------- CONFIG -------------------------
random.seed(42)
DRY_THRESHOLD = 30.0
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
SENSOR_UPDATE_INTERVAL = 3  # seconds
CENTER_DEFAULT = (12.969, 79.159)  # VIT Vellore

# ------------------------- DATA CLASS -------------------------
@dataclass
class Sensor:
    id: str
    lat: float
    lon: float
    moisture: float

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
            s.moisture = max(0, min(100, s.moisture + random.uniform(-5, 3)))
            mqtt_publish(s)
        time.sleep(SENSOR_UPDATE_INTERVAL)

# ------------------------- HELPERS -------------------------
def km_to_deg_lat(km): return km / 111.0
def km_to_deg_lon(km, lat): return km / (111.0 * max(0.1, math.cos(math.radians(lat))))
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(a))

def total_path_length_km(points):
    return sum(haversine(points[i][0], points[i][1],
                         points[i + 1][0], points[i + 1][1])
               for i in range(len(points) - 1)) if len(points) > 1 else 0

def nearest_neighbor_route(coords):
    n = len(coords)
    unvisited = set(range(1, n))
    route = [0]; current = 0
    while unvisited:
        nxt = min(unvisited, key=lambda j: haversine(
            coords[current][0], coords[current][1],
            coords[j][0], coords[j][1]))
        route.append(nxt)
        unvisited.remove(nxt)
        current = nxt
    route.append(0)
    return route

def two_opt(route, coords, max_iters=200):
    best = route[:]
    best_len = total_path_length_km([coords[i] for i in best])
    improved = True
    iters = 0
    while improved and iters < max_iters:
        improved = False
        iters += 1
        for i in range(1, len(best) - 2):
            for k in range(i + 1, len(best) - 1):
                new_route = best[:i] + best[i:k + 1][::-1] + best[k + 1:]
                new_len = total_path_length_km([coords[j] for j in new_route])
                if new_len < best_len:
                    best, best_len, improved = new_route, new_len, True
    return best

def sample_point_in_disc(lat0, lon0, radius_km):
    r = radius_km * math.sqrt(random.random())
    theta = random.random() * 2 * math.pi
    return (lat0 + km_to_deg_lat(r) * math.sin(theta),
            lon0 + km_to_deg_lon(r, lat0) * math.cos(theta))

def random_sensors(n, center_lat, center_lon, radius_km):
    return [
        Sensor(
            id=f"SENSOR_{i + 1}",
            lat=sample_point_in_disc(center_lat, center_lon, radius_km)[0],
            lon=sample_point_in_disc(center_lat, center_lon, radius_km)[1],
            moisture=random.uniform(0, 100)
        ) for i in range(n)
    ]

# ------------------------- SIMULATION -------------------------
def run_simulation(center_lat, center_lon, radius_km, n_sensors,
                   tile_area_mm2, power_per_sensor_mV):
    global sensors
    sensors = random_sensors(n_sensors, center_lat, center_lon, radius_km)
    dry = [s for s in sensors if s.moisture < DRY_THRESHOLD]

    DEPOT = {"lat": center_lat, "lon": center_lon}
    coords = [(DEPOT["lat"], DEPOT["lon"])] + [(s.lat, s.lon) for s in dry]
    route_idx = two_opt(nearest_neighbor_route(coords), coords)
    nn_dist = total_path_length_km([coords[i] for i in nearest_neighbor_route(coords)])
    opt_dist = total_path_length_km([coords[i] for i in route_idx])

    total_area_m2 = (tile_area_mm2 * n_sensors) / 1_000_000
    total_power = power_per_sensor_mV * n_sensors
    optimized_power = total_power * (opt_dist / nn_dist if nn_dist else 1)

    # Automatically calculate power station capacity
    station_power_mV = power_per_sensor_mV * 10
    num_stations = math.ceil(total_power / station_power_mV)
    total_station_output = num_stations * station_power_mV

    # Generate visible station coordinates
    power_stations = []
    for i in range(num_stations):
        lat_offset = random.uniform(-radius_km / 2, radius_km / 2)
        lon_offset = random.uniform(-radius_km / 2, radius_km / 2)
        lat = center_lat + km_to_deg_lat(lat_offset)
        lon = center_lon + km_to_deg_lon(lon_offset, center_lat)
        power_stations.append((lat, lon))

    # MAP 1: All Sensors
    m1 = folium.Map(location=[center_lat, center_lon], zoom_start=15)
    for s in sensors:
        color = "red" if s.moisture < DRY_THRESHOLD else "orange" if s.moisture < 60 else "green"
        folium.Marker(
            [s.lat, s.lon],
            popup=f"{s.id}: {s.moisture:.1f}% | {power_per_sensor_mV:.0f} mV",
            icon=folium.Icon(color=color)
        ).add_to(m1)

    # MAP 2: Route Optimized View
    m2 = folium.Map(location=[center_lat, center_lon], zoom_start=15)
    route_coords = [coords[i] for i in route_idx]
    folium.PolyLine(route_coords, color="blue", weight=4).add_to(m2)
    for s in dry:
        folium.Marker(
            [s.lat, s.lon],
            popup=f"{s.id}: dry {s.moisture:.1f}%",
            icon=folium.Icon(color="red")
        ).add_to(m2)

    # MAP 3: Power Station Planning View
    m3 = folium.Map(location=[center_lat, center_lon], zoom_start=15)
    for i, (lat, lon) in enumerate(power_stations, 1):
        folium.Marker(
            [lat, lon],
            popup=f"Power Station #{i}\nOutput: {station_power_mV:.0f} mV",
            icon=folium.Icon(color="purple", icon="info-sign")
        ).add_to(m3)

    for s in sensors:
        color = "red" if s.moisture < DRY_THRESHOLD else "green"
        folium.Marker(
            [s.lat, s.lon],
            popup=f"{s.id}: {s.moisture:.1f}%",
            icon=folium.Icon(color=color)
        ).add_to(m3)

    return (
        m1._repr_html_(),
        m2._repr_html_(),
        m3._repr_html_(),
        len(sensors), len(dry),
        nn_dist, opt_dist,
        total_area_m2, total_power, optimized_power,
        num_stations, total_station_output, station_power_mV
    )

# ------------------------- FLASK -------------------------
app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    summary = None
    map_all = map_route = map_power = None
    if request.method == "POST":
        center_lat = float(request.form["center_lat"])
        center_lon = float(request.form["center_lon"])
        radius_km = float(request.form["radius_km"])
        n_sensors = int(request.form["n_sensors"])
        tile_area_mm2 = float(request.form["tile_area_mm2"])
        power_per_sensor_mV = float(request.form["power_per_sensor_mV"])

        res = run_simulation(center_lat, center_lon, radius_km,
                             n_sensors, tile_area_mm2, power_per_sensor_mV)
        (map_all, map_route, map_power,
         n_total, n_dry, nn_d, opt_d,
         area, tot_p, opt_p, n_st, st_out, st_cap) = res
        summary = {
            "n_sensors": n_total, "dry_count": n_dry,
            "nn_distance": round(nn_d, 3), "opt_distance": round(opt_d, 3),
            "total_area": round(area, 4),
            "total_power": round(tot_p, 2),
            "optimized_power": round(opt_p, 2),
            "stations_needed": n_st,
            "station_output": round(st_out, 2),
            "station_capacity": round(st_cap, 2)
        }

    return render_template("index.html",
                           summary=summary,
                           map_all=map_all,
                           map_route=map_route,
                           map_power=map_power)

# ------------------------- RUN -------------------------
if __name__ == "__main__":
    threading.Thread(target=mqtt_loop, daemon=True).start()
    app.run(debug=True)
