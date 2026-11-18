import os
import time
import logging
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request

from rating_engine import classify_product

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "development-secret")

API_KEY = os.getenv("BRIGHTDATA_API_KEY", "").strip()
BASE_URL = "https://api.brightdata.com/datasets/v3"

logging.basicConfig(level=logging.INFO)


# Supported shopping websites
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


def valid_product_url(url):
    parsed = urlparse(url)

    return (
        parsed.scheme in ("https", "http")
        and bool(parsed.hostname)
    )


def resolve_product_url(url):
    """
    Try to expand shortened shopping URLs.
    If expansion fails, retain the original URL.
    """
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
        app.logger.warning("Could not expand shortened URL.")

    return url


def identify_marketplace(url):
    host = (urlparse(url).hostname or "").lower()

    for domain, config in MARKETPLACES.items():

        if host == domain or host.endswith("." + domain):
            name, env_key = config
            dataset_id = os.getenv(env_key, "").strip()

            if not dataset_id:
                raise ValueError(
                    f"{name} is recognised, but its Bright Data "
                    "dataset ID is not configured in .env."
                )

            return name, dataset_id

    raise ValueError(
        "This shopping website is not configured yet. "
        "A supported Bright Data scraper is required."
    )


def api_headers():
    if not API_KEY:
        raise RuntimeError(
            "Bright Data API key is missing. Check your .env file."
        )

    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


def request_product_data(url, dataset_id):
    """
    Submit one product URL to Bright Data.
    Handle both immediate and asynchronous responses.
    """

    response = requests.post(
        f"{BASE_URL}/scrape",
        params={
            "dataset_id": dataset_id,
            "format": "json"
        },
        headers=api_headers(),
        json={
            "input": [
                {"url": url}
            ]
        },
        timeout=90
    )

    # Include the provider's actual error message.
    if response.status_code not in (200, 202):
        raise RuntimeError(
            f"Bright Data returned HTTP {response.status_code}: "
            f"{response.text[:1500]}"
        )

    # Immediate result
    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            raise RuntimeError(
                "Bright Data returned an invalid JSON response."
            )

    # Asynchronous result
    try:
        snapshot_id = response.json().get("snapshot_id")
    except ValueError:
        snapshot_id = None

    if not snapshot_id:
        raise RuntimeError(
            "Bright Data did not return a snapshot ID."
        )

    # Check job status
    for attempt in range(24):

        time.sleep(5)

        progress = requests.get(
            f"{BASE_URL}/progress/{snapshot_id}",
            headers=api_headers(),
            timeout=30
        )

        progress.raise_for_status()

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
                headers=api_headers(),
                timeout=60
            )

            result.raise_for_status()
            return result.json()

        if status == "failed":
            raise RuntimeError(
                "Bright Data could not process this product URL."
            )

    raise RuntimeError(
        "Product retrieval is taking too long. Please try again later."
    )


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

        # Product average rating fields
        rating = first_value(item, [
            "rating",
            "product_rating",
            "star_rating",
            "average_rating",
            "rating_value"
        ])

        # Rating count fields
        count = first_value(item, [
    "rating_count",
    "ratings_count",
    "number_of_ratings",
    "ratingCount",
    "total_ratings",
    "ratings_total",
    "reviews_count"
])

        if rating is None or count is None:
            app.logger.warning(
                "Returned product fields: %s",
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

            return {
                "title": (
                    item.get("title")
                    or item.get("name")
                    or "Product"
                ),
                "rating": rating,
                "rating_count": count
            }

    raise ValueError(
        "Bright Data returned product data, but the rating fields "
        "were not recognised. Check the actual output field names "
        "in your Bright Data scraper."
    )


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
                # Expand shortened links when possible
                final_url = resolve_product_url(product_url)

                # Identify the shopping website
                platform, dataset_id = identify_marketplace(
                    final_url
                )

                # Retrieve product data
                raw_data = request_product_data(
                    final_url,
                    dataset_id
                )

                # Extract rating and rating count
                product = extract_product_data(raw_data)

                # Classify the product
                result = classify_product(
                    product["rating"],
                    product["rating_count"]
                )

                return render_template(
                    "result.html",
                    product_url=final_url,
                    platform=platform,
                    product_title=product["title"],
                    rating=product["rating"],
                    rating_count=product["rating_count"],
                    result=result
                )

            except (ValueError, RuntimeError) as exc:

                error = str(exc)

            except requests.HTTPError as exc:

                app.logger.exception(
                    "Bright Data HTTP error"
                )

                details = (
                    exc.response.text[:1500]
                    if exc.response is not None
                    else str(exc)
                )

                error = f"API HTTP Error: {details}"

            except requests.RequestException as exc:

                app.logger.exception(
                    "Network connection error"
                )

                error = (
                    "Could not connect to Bright Data. "
                    "Check your internet connection and try again."
                )

            except Exception:

                app.logger.exception(
                    "Unexpected application error"
                )

                error = (
                    "Something went wrong while analysing "
                    "this product. Check the terminal."
                )

    return render_template(
        "index.html",
        error=error
    )


if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "true").lower() == "true"
    )
