from spyne import Application, rpc, ServiceBase, Integer, Float, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server
import json
from spyne import Unicode  
from graphql_client import get_vehicle_list  # récupère les véhicules depuis l'API

# Charger les véhicules
with open("vehicules.json") as f:
    VEHICLES = json.load(f)


class TravelResultExtended(ComplexModel):
    total_time_minutes = Float(default=0)
    driving_time_minutes = Float(default=0)
    charging_time_minutes = Float(default=0)
    stops = Integer(default=0)


class TravelService(ServiceBase):

    @rpc(Unicode, Float, Float, _returns=TravelResultExtended)
    def calculate_travel_time(ctx, vehicle_id, distance_km, charging_power_kw):
        """
        distance_km : distance totale du trajet
        charging_power_kw : puissance moyenne des bornes
        """

        if distance_km <= 0:
            return TravelResultExtended(
    total_time_minutes=0,
    driving_time_minutes=0,
    charging_time_minutes=0,
    stops=0
)

        vehicle = next((v for v in VEHICLES if v["id"] == vehicle_id), None)
        if not vehicle:
            return TravelResultExtended(
    total_time_minutes=-1,
    driving_time_minutes=-1,
    charging_time_minutes=-1,
    stops=-1
)


        autonomy = vehicle["autonomy_km"]
        battery_kwh = vehicle["battery_kwh"]

        # 🚗 Temps de conduite (100 km/h)
        driving_time_minutes = (distance_km / 100) * 60

        # 🔌 Nombre d'arrêts
        stops = int(distance_km // autonomy)
        if distance_km % autonomy == 0 and stops > 0:
            stops -= 1

        # 🔋 Temps de recharge
        energy_per_charge = battery_kwh * 0.7  # 10% → 80%
        charging_minutes_per_stop = (energy_per_charge / charging_power_kw) * 60
        charging_time_minutes = stops * charging_minutes_per_stop

        total_time_minutes = driving_time_minutes + charging_time_minutes

        return TravelResultExtended(
            total_time_minutes=round(total_time_minutes),
            driving_time_minutes=round(driving_time_minutes),
            charging_time_minutes=round(charging_time_minutes),
            stops=stops
        )

    @rpc(Unicode, Float, Float, Float, _returns=TravelResultExtended)
    def calculate_travel_time_detailed(ctx, vehicle_id, distance_km, battery_kwh, charging_power_kw):
        if distance_km <= 0:
            return TravelResultExtended(0, 0, 0, 0)

        # 🔹 Récupérer les véhicules directement depuis l'API
        VEHICLES = get_vehicle_list()
        print("All VEHICLES IDs:", [v["id"] for v in VEHICLES])
        print("Received vehicle_id:", vehicle_id)

        # 🔹 Cherche le véhicule correspondant à l'ID
        vehicle = next((v for v in VEHICLES if str(v["id"]).strip() == str(vehicle_id).strip()), None)
        print("All VEHICLES IDs:", [v["id"] for v in VEHICLES])
        print("Received vehicle_id:", vehicle_id)
        print(vehicle)

        if not vehicle:
            print("Véhicule introuvable")
            return TravelResultExtended(-1, -1, -1, -1)

        autonomy = vehicle["range"]["chargetrip_range"]["worst"]
        battery_kwh = vehicle["battery"]["usable_kwh"]

        # utiliser battery_kwh passé par le client
        driving_time_minutes = (distance_km / 100) * 60
        stops = int(distance_km // autonomy)
        if distance_km % autonomy == 0 and stops > 0:
            stops -= 1

        charging_minutes_per_stop = (battery_kwh * 0.7 / charging_power_kw) * 60
        charging_time_minutes = stops * charging_minutes_per_stop
        total_time_minutes = driving_time_minutes + charging_time_minutes

        return TravelResultExtended(
    total_time_minutes=float(round(total_time_minutes)),
    driving_time_minutes=float(round(driving_time_minutes)),
    charging_time_minutes=float(round(charging_time_minutes)),
    stops=int(stops)
)
application = Application(
    [TravelService],
    tns="travel.soap",
    in_protocol=Soap11(),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == "__main__":
    server = make_server("127.0.0.1", 8000, wsgi_application)
    print("SOAP server running on http://127.0.0.1:8000/?wsdl")
    server.serve_forever()
