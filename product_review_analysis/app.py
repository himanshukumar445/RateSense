import os
import time
import logging
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request

from rating_engine import classify_product


# ==================================================
# 1. CONFIGURATION
# ==================================================

load_dotenv()

app = Flask(__name__)

# Load Flask secret key
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()

if not SECRET_KEY:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing. Add it to your .env "
        "file or Render environment variables."
    )

app.secret_key = SECRET_KEY

# Load Bright Data API key
API_KEY = os.getenv("BRIGHTDATA_API_KEY", "").strip()

# Remove Bearer prefix if accidentally included in .env
if API_KEY.lower().startswith("bearer "):
    API_KEY = API_KEY[7:].strip()

# Bright Data API configuration
BASE_URL = "https://api.brightdata.com/datasets/v3"

logging.basicConfig(level=logging.INFO)


# ==================================================
# 2. BRIGHT DATA AUTHENTICATION DIAGNOSTIC
# ==================================================

print("========== BRIGHT DATA CHECK ==========", flush=True)
print("API KEY LOADED:", bool(API_KEY), flush=True)
print("API KEY LENGTH:", len(API_KEY), flush=True)

if API_KEY:

    try:
        test_response = requests.get(
            "https://api.brightdata.com/status",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Accept": "application/json"
            },
            timeout=20
        )

        print(
            "BRIGHT DATA STATUS:",
            test_response.status_code,
            flush=True
        )

        print(
            "BRIGHT DATA RESPONSE:",
            test_response.text[:300],
            flush=True
        )

    except requests.RequestException as e:

        print(
            "BRIGHT DATA TEST ERROR:",
            str(e),
            flush=True
        )

else:
    print("BRIGHT DATA TEST SKIPPED: API key missing.", flush=True)

print("========================================", flush=True)


# ==================================================
# 3. SUPPORTED SHOPPING WEBSITES
# ==================================================

MARKETPLACES = {
    "amazon.in": ("Amazon India", "AMAZON_DATASET_ID"),
    "amzn.in": ("Amazon India", "AMAZON_DATASET_ID"),
    "amazon.com": ("Amazon", "AMAZON_DATASET_ID"),
    "flipkart.com": ("Flipkart", "FLIPKART_DATASET_ID"),
    "myntra.com": ("Myntra", "MYNTRA_DATASET_ID"),
    "meesho.com": ("Meesho", "MEESHO_DATASET_ID"),
    "ajio.com": ("AJIO", "AJIO_DATASET_ID"),
    "walmart.com": ("Walmart", "WALMART_DATASET_ID"),
}


# ==================================================
# 4. VALIDATE PRODUCT URL
# ==================================================

def valid_product_url(url):

    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("https", "http")
            and bool(parsed.hostname)
        )

    except ValueError:
        return False


# ==================================================
# 5. EXPAND SHORTENED PRODUCT URLS
# ==================================================

def resolve_product_url(url):

    try:
        response = requests.get(
            url,
            allow_redirects=True,
            timeout=15,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/120 Safari/537.36"
                )
            }
        )

        if response.url:
            return response.url

    except requests.RequestException:

        app.logger.warning(
            "Could not expand the supplied product URL."
        )

    return url


# ==================================================
# 6. IDENTIFY SHOPPING WEBSITE
# ==================================================

def identify_marketplace(url):

    host = (urlparse(url).hostname or "").lower()

    for domain, config in MARKETPLACES.items():

        if host == domain or host.endswith("." + domain):

            name, env_key = config

            dataset_id = os.getenv(env_key, "").strip()

            if not dataset_id:

                raise ValueError(
                    f"{name} is recognised, but its dataset ID "
                    f"({env_key}) is missing from the environment."
                )

            return name, dataset_id

    raise ValueError(
        "This shopping website is not configured yet. "
        "A compatible Bright Data scraper is required."
    )


# ==================================================
# 7. BRIGHT DATA API HEADERS
# ==================================================

def api_headers():

    if not API_KEY:

        raise RuntimeError(
            "Bright Data API key is missing. "
            "Add BRIGHTDATA_API_KEY in Render Environment Variables."
        )

    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


# ==================================================
# 8. HANDLE API ERRORS
# ==================================================

def check_api_response(response):

    if response.ok:
        return

    status_code = response.status_code

    try:
        details = response.json()

    except ValueError:
        details = response.text[:1000]

    app.logger.error(
        "Bright Data API returned HTTP %s: %s",
        status_code,
        str(details)[:1000]
    )

    if status_code == 401:

        raise RuntimeError(
            "Bright Data authentication failed (HTTP 401). "
            "Check the API key in Render Environment Variables."
        )

    if status_code == 403:

        raise RuntimeError(
            "Bright Data access denied (HTTP 403). "
            "Check account permissions and scraper access."
        )

    if status_code == 404:

        raise RuntimeError(
            "Bright Data could not find the requested resource. "
            "Check the dataset ID or snapshot ID."
        )

    raise RuntimeError(
        f"Bright Data returned HTTP {status_code}: "
        f"{str(details)[:1000]}"
    )


# ==================================================
# 9. REQUEST PRODUCT DATA
# ==================================================

def request_product_data(url, dataset_id):

    headers = api_headers()

    endpoint = f"{BASE_URL}/scrape"

    payload = {
        "input": [
            {"url": url}
        ]
    }

    try:

        response = requests.post(
            endpoint,
            params={
                "dataset_id": dataset_id,
                "format": "json"
            },
            headers=headers,
            json=payload,
            timeout=90
        )

        check_api_response(response)

        # Immediate response
        if response.status_code == 200:
            return response.json()

        # Asynchronous response
        if response.status_code == 202:

            snapshot_id = response.json().get("snapshot_id")

            if not snapshot_id:

                raise RuntimeError(
                    "Bright Data did not return a snapshot ID."
                )

            app.logger.info(
                "Bright Data snapshot created successfully."
            )

            # Wait for scraping to finish
            for attempt in range(24):

                time.sleep(5)

                progress = requests.get(
                    f"{BASE_URL}/progress/{snapshot_id}",
                    headers=headers,
                    timeout=30
                )

                check_api_response(progress)

                status = progress.json().get("status")

                app.logger.info(
                    "Bright Data job status: %s (check %s)",
                    status,
                    attempt + 1
                )

                if status == "ready":

                    result = requests.get(
                        f"{BASE_URL}/snapshot/{snapshot_id}",
                        params={"format": "json"},
                        headers=headers,
                        timeout=60
                    )

                    check_api_response(result)

                    return result.json()

                if status == "failed":

                    raise RuntimeError(
                        "Bright Data could not process this product URL."
                    )

            raise RuntimeError(
                "Product retrieval is taking too long. "
                "Please try again later."
            )

        raise RuntimeError(
            f"Unexpected Bright Data response: {response.status_code}"
        )

    except requests.Timeout:

        raise RuntimeError(
            "Bright Data request timed out. Please try again."
        )

    except requests.ConnectionError:

        raise RuntimeError(
            "Could not connect to Bright Data. "
            "Please check the network and try again."
        )


# ==================================================
# 10. EXTRACT PRODUCT RATING AND COUNT
# ==================================================

def first_value(item, field_names):

    for field in field_names:

        value = item.get(field)

        if value is not None and value != "":
            return value

    return None


def extract_product_data(data):

    if isinstance(data, dict):
        items = [data]

    elif isinstance(data, list):
        items = data

    else:

        raise ValueError(
            "Unexpected data format returned by Bright Data."
        )

    for item in items:

        if not isinstance(item, dict):
            continue

        # Product average rating
        rating = first_value(item, [
            "rating",
            "product_rating",
            "star_rating",
            "average_rating",
            "rating_value"
        ])

        # Prefer actual rating count
        count = first_value(item, [
            "rating_count",
            "ratings_count",
            "number_of_ratings",
            "ratingCount",
            "total_ratings",
            "ratings_total"
        ])

        count_type = "rating_count"

        # Fallback to review count
        if count is None:

            count = first_value(item, [
                "reviews_count",
                "review_count"
            ])

            count_type = "review_count"

        if rating is None or count is None:

            app.logger.warning(
                "Product rating fields not recognised. "
                "Returned fields: %s",
                list(item.keys())
            )

            continue

        try:

            rating = float(
                str(rating).replace(",", "").strip()
            )

            count = int(
                str(count).replace(",", "").replace("+", "").strip()
            )

        except (ValueError, TypeError):
            continue

        if 1 <= rating <= 5 and count >= 0:

            if count_type == "review_count":

                app.logger.warning(
                    "Using review count as a proxy for rating volume."
                )

            return {
                "title": (
                    item.get("title")
                    or item.get("name")
                    or "Product"
                ),
                "rating": rating,
                "rating_count": count,
                "count_type": count_type
            }

    raise ValueError(
        "Bright Data returned product data, but the rating fields "
        "were not recognised. Check the scraper output fields."
    )


# ==================================================
# 11. MAIN FLASK ROUTE
# ==================================================

@app.route("/", methods=["GET", "POST"])
def index():

    error = None

    if request.method == "POST":

        product_url = request.form.get(
            "product_url", ""
        ).strip()

        if not valid_product_url(product_url):

            error = "Please enter a valid product URL."

        else:

            try:

                # Expand shortened URL
                final_url = resolve_product_url(product_url)

                # Identify shopping website
                platform, dataset_id = identify_marketplace(
                    final_url
                )

                # Retrieve product information
                raw_data = request_product_data(
                    final_url,
                    dataset_id
                )

                # Extract product rating
                product = extract_product_data(raw_data)

                # Classify product
                result = classify_product(
                    product["rating"],
                    product["rating_count"]
                )

                # Display result page
                return render_template(
                    "result.html",
                    product_url=final_url,
                    platform=platform,
                    product_title=product["title"],
                    rating=product["rating"],
                    rating_count=product["rating_count"],
                    count_type=product["count_type"],
                    result=result
                )

            except (ValueError, RuntimeError) as exc:

                error = str(exc)

            except requests.RequestException:

                app.logger.exception(
                    "Bright Data network error"
                )

                error = (
                    "Could not connect to Bright Data. "
                    "Please try again later."
                )

            except Exception:

                app.logger.exception(
                    "Unexpected application error"
                )

                error = (
                    "Something went wrong while analysing "
                    "this product. Check the application logs."
                )

    return render_template(
        "index.html",
        error=error
    )


# ==================================================
# 12. RUN APPLICATION
# ==================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true"
    )
