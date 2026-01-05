import requests

API_URL = "https://opendata.reseaux-energies.fr/api/records/1.0/search/"
 
def get_nearby_charging_stations(lat, lon, radius=10000):
    """
    Récupère les bornes de recharge à proximité d'une position GPS.

    Args:
        lat (float): Latitude de la position de recherche
        lon (float): Longitude de la position de recherche
        radius (int): Rayon de recherche en mètres (par défaut 5000m = 5km)

    Returns:
        list: Liste des stations avec leurs informations
    """

    # Vérification des coordonnées
    if lat is None or lon is None:
        print("❌ Coordonnées invalides : lat ou lon est None")
        return []

    try:
        lat = float(lat)
        lon = float(lon)
        radius = int(radius)
    except ValueError:
        print("❌ Coordonnées invalides : impossible de convertir en float/int")
        return []

    # DEBUG : vérifier ce qui est envoyé à l'API
    #print(f"DEBUG: lat={lat}, lon={lon}, radius={radius}")

    params = {
        "dataset": "bornes-irve",
        "geofilter.distance": f"{lat},{lon},{radius}",  # format correct
        "rows": 1000
    }
    # 🔹 PRINT DE DEBUG : vérifie les paramètres envoyés
    #print("DEBUG: Appel API avec params =", params)

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        #print(data)

        stations = []
        seen_coords = set()  # pour éviter doublons

        for rec in data.get("records", []):
            fields = rec.get("fields", {})
            coords = fields.get("geo_point_borne")
            if not coords or len(coords) != 2:
                continue

            coord_tuple = tuple(coords)
            if coord_tuple in seen_coords:
                continue
            seen_coords.add(coord_tuple)

            name = fields.get("nom_operateur") or fields.get("n_enseigne") or "Opérateur inconnu"
            address = fields.get("adresse_station") or fields.get("ad_station") or "Adresse inconnue"
            city = fields.get("commune") or "Ville inconnue"
            access = fields.get("accessibilite") or fields.get("acces_recharge") or "Non spécifié"
            raw_power = fields.get("puiss_max")

            try:
                puissance = float(raw_power)
            except (TypeError, ValueError):
                puissance = 50.0  # valeur réaliste par défaut


            station = {
                "name": name,
                "address": address,
                "city": city,
                "coordinates": coords,
                "access": access,
                "puissance": puissance
            }
            stations.append(station)

       # print(f"✅ {len(stations)} borne(s) uniques avec coordonnées valides")
        return stations

    except requests.exceptions.HTTPError as e:
        print(f"❌ Erreur HTTP {e.response.status_code}: {e}")
        print(f"📄 Réponse: {e.response.text[:500]}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur lors de la requête : {e}")
        return []
    except Exception as e:
        print(f"❌ Erreur lors du traitement des données : {e}")
        import traceback
        traceback.print_exc()
        return []



def geocode_address(address):
    """Convertit une adresse en coordonnées GPS (lat, lon)."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address,
        "format": "json",
        "limit": 1
    }
    response = requests.get(url, params=params, headers={"User-Agent": "EVTravelPlanner"})
    response.raise_for_status()
    data = response.json()
    if data:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        return lat, lon
    return None, None


