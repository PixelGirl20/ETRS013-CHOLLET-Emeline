from spyne import Application, rpc, ServiceBase, Integer, Float, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server

import json

# Charger les véhicules
with open("vehicules.json") as f:
    VEHICLES = json.load(f)
# Exemple simple de véhicules


class TravelResult(ComplexModel):
    total_time = Float
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
        print("autonomy : ",autonomy)
        charging_time = vehicle["charging_time_h"]
        print("charging time : ",charging_time)

        stops = int(distance_km // autonomy)
        print("stops  : ",stops)
        if distance_km % autonomy == 0 and stops > 0:
            stops -= 1

        driving_time = float(distance_km) / 100.0
        total_time = float(driving_time + (stops * charging_time))
        #print(total_time,stops)
        return TravelResult(total_time=total_time, stops=int(stops))

# Application SOAP
application = Application([TravelService],
                          tns='spyne.examples.travel',
                          in_protocol=Soap11(),
                          out_protocol=Soap11())

wsgi_application = WsgiApplication(application)

if __name__ == "__main__":
    server = make_server('127.0.0.1', 8000, wsgi_application)
    print("SOAP server running on http://127.0.0.1:8000/?wsdl")
    server.serve_forever()