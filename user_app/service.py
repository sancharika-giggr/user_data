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


def convert_to_dict_of_lists(input_list):
    result_dict = {}
    current_category = None

    for item in input_list:
        if item.startswith('Category'):
            current_category = item.replace('Category ', '').split(': ')[1].strip()
            result_dict[current_category] = []
        elif item.startswith('Keywords'):
            keywords = item.replace('Keywords ', '').split(': ')[1].strip()
            result_dict[current_category] = [keyword.strip() for keyword in keywords.split(', ')]

    return result_dict

