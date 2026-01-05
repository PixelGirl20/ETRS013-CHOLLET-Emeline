from flask import Flask, request, render_template
from zeep import Client
from rest_client import get_nearby_charging_stations
import folium
import os
from graphql_client import get_vehicle_list
from rest_client import geocode_address


app = Flask(__name__)
wsdl = "http://127.0.0.1:8000/?wsdl"  # Le SOAP server doit déjà tourner
soap_client = Client(wsdl=wsdl)

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    if request.method == "POST":
        try:
            vehicle_id = int(request.form["vehicle_id"])
            distance_km = float(request.form["distance_km"])
            soap_result = soap_client.service.calculate_travel_time(vehicle_id, distance_km)
            result = {"total_time": soap_result.total_time, "stops": soap_result.stops}
            print(soap_result)
        except Exception as e:
            error = str(e)
    return render_template("index.html", result=result, error=error)


# ----------------------------
#    🔥 NOUVELLE ROUTE REST
# ----------------------------
from geopy.distance import geodesic
import openrouteservice
from openrouteservice import convert

ORS_API_KEY = "eyJvcmciOiI1YjNjZTM1OTc4NTExMTAwMDFjZjYyNDgiLCJpZCI6IjllZGIwMjJjYTFiZTRkM2Q5NjBiOTU3NWM3Njg0Zjc4IiwiaCI6Im11cm11cjY0In0="  # 🔑 remplace par ta clé ORS

@app.route("/bornes", methods=["GET", "POST"])
def bornes():
    stations = []
    error = None
    map_generated = False
    debug_msg = None

    cars = get_vehicle_list()  # voitures ChargeTrip

    total_time = None
    driving_time = None
    charge_time = None
    stops = []
    total_time_str = None
    charge_time_str = None
    driving_time_str = None
    total_distance_km = None

    if request.method == "POST":
        start_address = request.form.get("start_address")
        end_address = request.form.get("end_address")
        vehicle_id = request.form.get("vehicle_id")

        if not start_address or not end_address:
            error = "Veuillez fournir une adresse de départ et une adresse d'arrivée."

        elif not vehicle_id:
            error = "Veuillez sélectionner un véhicule."

        else:
            selected_car = next((c for c in cars if c["id"] == vehicle_id), None)

            if not selected_car:
                error = "Véhicule introuvable."

            else:
                start_coords = geocode_address(start_address)
                end_coords = geocode_address(end_address)

                if start_coords == (None, None):
                    error = f"Impossible de géocoder l'adresse de départ : {start_address}"
                elif end_coords == (None, None):
                    error = f"Impossible de géocoder l'adresse d'arrivée : {end_address}"
                else:
                    # ===============================
                    # 🗺️ Carte
                    # ===============================
                    m = folium.Map(location=start_coords, zoom_start=12)
                    folium.Marker(start_coords, tooltip="Départ", icon=folium.Icon(color="blue")).add_to(m)
                    folium.Marker(end_coords, tooltip="Arrivée", icon=folium.Icon(color="red")).add_to(m)

                    # ===============================
                    # 🚗 Itinéraire ORS
                    # ===============================
                    client = openrouteservice.Client(key=ORS_API_KEY)
                    # 🔹 Route simple pour calcul distance / temps
                    simple_route = client.directions(
                        coordinates=[start_coords[::-1], end_coords[::-1]],
                        profile="driving-car",
                        format="geojson"
                    )

                    segment = simple_route["features"][0]["properties"]["segments"][0]
                    
                    driving_time = round(segment["duration"] / 60)

                    route_coords = [
                        (pt[1], pt[0])
                        for pt in simple_route["features"][0]["geometry"]["coordinates"]
                    ]

                    final_segment = simple_route["features"][0]["properties"]["segments"]

                    # Distance totale en km (tous segments cumulés)
                    total_distance_km = sum(seg["distance"] for seg in final_segment) / 1000
                    total_distance_km = round(total_distance_km, 1)

                    # ===============================
                    # 🔌 Bornes le long du trajet
                    # ===============================
                    all_stations = []
                    seen = set()

                    for point in route_coords[::50]:
                        nearby = get_nearby_charging_stations(point[0], point[1], radius=5000)
                        for s in nearby:
                            coord_key = tuple(s["coordinates"])
                            if coord_key in seen:
                                continue
                            seen.add(coord_key)
                            all_stations.append(s)

                    charging_stations = find_charging_stops(
                    route_coords,
                    selected_car["range"]["chargetrip_range"]["worst"],
                    all_stations
                    )
                    stations = charging_stations

                    for s in stations:
                        folium.Marker(
                            s["coordinates"],
                            tooltip=s["name"],
                            popup=f"{s['address']}<br>{s['city']}<br>⚡ {s['puissance']} kW",
                            icon=folium.Icon(color="green", icon="flash")
                        ).add_to(m)

                    # ===============================
                    # 🧭 Waypoints = départ → bornes → arrivée
                    # ===============================
                    waypoints = [start_coords]

                    for s in charging_stations:
                        waypoints.append(tuple(s["coordinates"]))

                    waypoints.append(end_coords)

                    # ORS attend (lon, lat)
                    waypoints = [(p[1], p[0]) for p in waypoints]

                    route = client.directions(
                    coordinates=waypoints,
                    profile="driving-car",
                    format="geojson"
                )
                    # ===============================
                    # 🟢 Tracé final AVEC bornes
                    # ===============================
                    final_route_coords = [
                        (pt[1], pt[0])
                        for pt in route["features"][0]["geometry"]["coordinates"]
                    ]

                    folium.PolyLine(
                        final_route_coords,
                        color="green",
                        weight=5,
                        opacity=0.8
                    ).add_to(m)

                    # ===============================
                    # 🔍 Auto-zoom sur l’ensemble du trajet
                    # ===============================
                    lats = [pt[0] for pt in final_route_coords]
                    lons = [pt[1] for pt in final_route_coords]

                    bounds = [
                        [min(lats), min(lons)],
                        [max(lats), max(lons)]
                    ]

                    m.fit_bounds(bounds, padding=(60, 60))

                    map_path = os.path.join(app.root_path, "static", "map.html")
                    m.save(map_path)
                    map_generated = True
                    # ===============================
                    # ⚡ CALCUL TEMPS DE RECHARGE
                    # ===============================
                    
                    battery_kwh = selected_car["battery"]["usable_kwh"]

                    charge_time = 0
                    stops = []

                    for station in charging_stations:
                        power = float(station.get("puissance", 50))  # kW
                        energy = battery_kwh * 0.7  # 10% → 80%
                        minutes = (energy / power) * 60

                        charge_time += minutes

                        station["recharge_minutes"] = round(minutes)


                    # total_time en minutes
                    total_time = round(driving_time + charge_time)

                    # Conversion en heures + minutes
                    hours = total_time // 60
                    minutes = total_time % 60

                    # Formattage sous forme "H h M min"
                    total_time_str = f"{hours} h {minutes} " if hours > 0 else f"{minutes} "

                    # Pareil pour charge_time
                    charge_time = round(charge_time)
                    charge_hours = charge_time // 60
                    charge_minutes = charge_time % 60
                    charge_time_str = f"{charge_hours} h {charge_minutes} " if charge_hours > 0 else f"{charge_minutes} "

                    # Pareil pour driving_time
                    driving_time = round(driving_time)
                    driving_hours = driving_time // 60
                    driving_minutes = driving_time % 60
                    driving_time_str = f"{driving_hours} h {driving_minutes} " if driving_hours > 0 else f"{driving_minutes} "


    return render_template(
    "bornes.html",
    stations=stations,
    cars=cars,
    error=error,
    map_generated=map_generated,
    debug_msg=debug_msg,
    total_time=total_time_str,      
    driving_time=driving_time_str,
    charge_time=charge_time_str,  
    total_distance=total_distance_km,  
    stops=stops
)



from geopy.distance import geodesic

@app.route("/routes", methods=["GET", "POST"])
def routes():
    stations = []
    error = None
    map_generated = False
    debug_msg = None
    print(f"✅ map_generated = {map_generated}")
    if request.method == "POST":
        start_address = request.form.get("start_address")
        end_address = request.form.get("end_address")

        start_coords = geocode_address(start_address)
        end_coords = geocode_address(end_address)
        print(f"DEBUG: start_coords={start_coords}, end_coords={end_coords}")

        if start_coords == (None, None):
            error = f"Impossible de géocoder l'adresse de départ : {start_address}"
        elif end_coords == (None, None):
            error = f"Impossible de géocoder l'adresse d'arrivée : {end_address}"
        else:
            # Génération de la carte centrée sur le départ
            m = folium.Map(location=start_coords, zoom_start=12)
            folium.Marker(start_coords, tooltip="Départ", icon=folium.Icon(color="blue")).add_to(m)
            folium.Marker(end_coords, tooltip="Arrivée", icon=folium.Icon(color="red")).add_to(m)
            folium.PolyLine([start_coords, end_coords], color="green", weight=5, opacity=0.7).add_to(m)

            # Recherche de bornes autour du départ et de l'arrivée
            points_to_check = [start_coords, end_coords]
            
            for point in points_to_check:
                nearby = get_nearby_charging_stations(point[0], point[1], radius=5000)
                for s in nearby:
                    if s["coordinates"]:
                        stations.append(s)
                        folium.Marker(
                            s["coordinates"],
                            tooltip=s["name"],
                            popup=f"{s['address']}<br>{s['city']}",
                            icon=folium.Icon(color="green")
                        ).add_to(m)

            map_path = os.path.join(app.root_path, "static", "map.html")
            m.save(map_path)
            map_generated = True
            

            debug_msg = f"Carte générée pour le trajet {start_address} → {end_address} avec {len(stations)} bornes."
       
    return render_template("routes.html", error=error, map_generated=map_generated, debug_msg=debug_msg, stations=stations,)


@app.route("/static_map")
def static_map():
    import os
    map_file = os.path.join(app.root_path, "static", "map.html")
    if os.path.exists(map_file):
        return app.send_static_file("map.html")
    else:
        return "Fichier de carte introuvable."

# --------------------------------
#    🔥 NOUVELLE ROUTE VEHICULE
# --------------------------------


@app.route("/vehicles")
def vehicles():
    try:
        cars = get_vehicle_list()
        print(cars)
        return render_template("vehicles.html", cars=cars)
    except Exception as e:
        return f"Erreur GraphQL : {e}"




def find_charging_stops(route_coords, autonomy_km, stations):
    """
    Sélectionne uniquement les bornes nécessaires le long du trajet
    """
    stops = []
    distance_since_last_stop = 0

    for i in range(1, len(route_coords)):
        prev = route_coords[i - 1]
        curr = route_coords[i]

        distance_since_last_stop += geodesic(prev, curr).km

        if distance_since_last_stop >= autonomy_km:
            # trouver la borne la plus proche de ce point
            closest = min(
                stations,
                key=lambda s: geodesic(curr, s["coordinates"]).km
            )

            stops.append(closest)
            distance_since_last_stop = 0

    return stops


if __name__ == "__main__":
    app.run(port=5050, debug=True)
