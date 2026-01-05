from spyne import Application, rpc, ServiceBase, Integer, Float, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server
import json

# Charger les véhicules
with open("vehicules.json") as f:
    VEHICLES = json.load(f)


class TravelResult(ComplexModel):
    total_time = Float
    stops = Integer


# ===== AJOUT : modèle étendu =====
class TravelResultExtended(ComplexModel):
    total_time_minutes = Float
    driving_time_minutes = Float
    charging_time_minutes = Float
    stops = Integer


# Service
class TravelService(ServiceBase):

    @rpc(Integer, Float, _returns=TravelResult)
    def calculate_travel_time(ctx, vehicle_id, distance_km):
        if distance_km <= 0:
            return TravelResult(total_time=0.0, stops=0)

        vehicle = next((v for v in VEHICLES if v["id"] == vehicle_id), None)
        if not vehicle:
            return TravelResult(total_time=-1.0, stops=-1)

        autonomy = vehicle["autonomy_km"]
        charging_time = vehicle["charging_time_h"]

        stops = int(distance_km // autonomy)
        if distance_km % autonomy == 0 and stops > 0:
            stops -= 1

        driving_time = float(distance_km) / 100.0
        total_time = float(driving_time + (stops * charging_time))

        return TravelResult(total_time=total_time, stops=int(stops))

    # ===== AJOUT : méthode SOAP détaillée =====
    @rpc(Integer, Float, Float, Float, _returns=TravelResultExtended)
    def calculate_travel_time_detailed(ctx, vehicle_id, distance_km, battery_kwh, charging_power_kw):

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

        driving_time_minutes = (distance_km / 100.0) * 60

        stops = int(distance_km // autonomy)
        if distance_km % autonomy == 0 and stops > 0:
            stops -= 1

        energy_kwh = battery_kwh * 0.7
        charging_minutes_per_stop = (energy_kwh / charging_power_kw) * 60
        charging_time_minutes = stops * charging_minutes_per_stop

        total_time_minutes = driving_time_minutes + charging_time_minutes

        return TravelResultExtended(
            total_time_minutes=round(total_time_minutes),
            driving_time_minutes=round(driving_time_minutes),
            charging_time_minutes=round(charging_time_minutes),
            stops=stops
        )


# Application SOAP
application = Application(
    [TravelService],
    tns='spyne.examples.travel',
    in_protocol=Soap11(),
    out_protocol=Soap11()
)

wsgi_application = WsgiApplication(application)

if __name__ == "__main__":
    server = make_server('127.0.0.1', 8000, wsgi_application)
    print("SOAP server running on http://127.0.0.1:8000/?wsdl")
    server.serve_forever()
