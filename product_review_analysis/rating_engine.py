
def get_evidence_level(rating_count):

    if rating_count == 0:
        return "No rating-volume evidence"

    elif rating_count < 100:
        return "Limited evidence"

    elif rating_count < 1000:
        return "Moderate evidence"

    else:
        return "Strong evidence"


def classify_product(average_rating, rating_count):

    if not 1 <= average_rating <= 5:
        raise ValueError("Rating must be between 1 and 5.")

    if rating_count < 0:
        raise ValueError("Rating count cannot be negative.")

    evidence = get_evidence_level(rating_count)

    if average_rating < 3.0:

        label = "BAD"
        color = "bad"

        explanation = (
            "The average customer rating is below 3 stars."
        )

    elif average_rating < 4.0:

        label = "AVERAGE"
        color = "average"

        explanation = (
            "The average customer rating is between 3 and 4 stars."
        )

    elif rating_count < 100:

        label = "AVERAGE"
        color = "average"

        explanation = (
            "The rating is high, but fewer than 100 ratings "
            "are available. More ratings are needed."
        )

    else:

        label = "GOOD"
        color = "good"

        explanation = (
            "The product has a rating of at least 4 stars "
            "and at least 100 customer ratings."
        )

    return {
        "label": label,
        "color": color,
        "explanation": explanation,
        "evidence": evidence
    }
