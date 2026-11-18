import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BRIGHTDATA_API_KEY", "").strip()

url = "https://api.brightdata.com/datasets/v3/scrape"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

params = {
    "dataset_id": "gd_l7q7dkf244hwjntr0",
    "format": "json"
}

payload = {
    "input": [
        {"url": "https://www.amazon.in/dp/B0CRMZHDG8"}
    ]
}

response = requests.post(
    url,
    headers=headers,
    params=params,
    json=payload,
    timeout=120
)

print("HTTP STATUS:", response.status_code)
print("RESPONSE:", response.text[:2000])
