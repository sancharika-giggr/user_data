import requests


def get_geo_location(ip_address):
    url = f"https://ipinfo.io/{ip_address}/json"
    response = requests.get(url)
    data = response.json()
    return data


def categorize_interests(interests, blog_categories):
    categorized_interests = []

    for interest in interests:
        for category in blog_categories:
            if any(keyword.lower() in interest.lower() for keyword in category.split()):
                categorized_interests.append(category)
                break

    return categorized_interests
