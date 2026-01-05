import requests

GRAPHQL_URL = "https://api.chargetrip.io/graphql"

# ⚠ Nécessite une clé API (Free) sur https://developers.chargetrip.com
APP_ID = "693c2f875e1f218f1f2c93ef"
CLIENT_ID = "693c2f875e1f218f1f2c93ed"

headers = {
    "Content-Type": "application/json",
    "x-client-id": CLIENT_ID,
    "x-app-id": APP_ID
}

def get_vehicle_list():
    query = """
    query {
      vehicleList(size: 20) {
        id
        naming {
          make
          model
          version
          edition
          chargetrip_version
        }
        battery {
          full_kwh
          usable_kwh
        }
        range {
          chargetrip_range {
            worst
            best
          }
        }
        media {
          image {
            thumbnail_url
          }
        }
      }
    }
    """

    response = requests.post(GRAPHQL_URL, json={"query": query}, headers=headers)
    response.raise_for_status()

    print("=== Réponse complète GraphQL ===")
    print(response.text)

    data = response.json()
    if "errors" in data:
        raise Exception(data["errors"][0]["message"])

    return data["data"]["vehicleList"]



