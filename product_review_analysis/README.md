
# Product Quality Rating System

This project analyses product quality using the average customer star rating and total number of ratings.

## Technologies

- Python
- Flask
- HTML
- CSS

## Inputs

1. Product URL
2. Average rating (1 to 5)
3. Total number of ratings

## Outputs

- GOOD
- AVERAGE
- BAD

## Classification Rules

- Below 3 stars: BAD
- 3 to below 4 stars: AVERAGE
- 4 stars or above with fewer than 100 ratings: AVERAGE
- 4 stars or above with at least 100 ratings: GOOD

## Run the Project

Install dependencies:

    pip install -r requirements.txt

Start the application:

    python app.py

Open in browser:

    http://127.0.0.1:5000

## Important

The application identifies the shopping platform from the product URL, but it does not automatically retrieve ratings. The user enters the average rating and total number of ratings displayed on the product page.

Automatic retrieval can be added later using an authorised API or data provider.
