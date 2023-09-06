import requests
from neo4j import GraphDatabase


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


def run_query(tx, query, input_dict):
    result = tx.run(query, input_dict=input_dict)
    return result.single()[0]


def save_dict_in_neo4j(uri, username, password, input_dict, database_name):
    # Connect to the Neo4j database
    with GraphDatabase.driver(uri, auth=(username, password),  database=database_name) as driver:
        with driver.session() as session:
            for subject, themes_dict in input_dict.items():
                # Create a node for the subject
                session.run("MERGE (s:Subject {name: $subject})", subject=subject)

                for theme, topic_list in themes_dict.items():
                    theme_name = f"{theme}+{subject}"
                    # Create a node for the theme
                    session.run("MERGE (t:Theme {name: $theme})", theme=theme_name)

                    session.run(
                        """
                        MATCH (s:Subject {name: $subject})
                        MATCH (t:Theme {name: $theme})
                        MERGE (s)-[:HAS_THEME]->(t)
                        """,
                        subject=subject, theme=theme_name
                    )

                    for topic in topic_list:
                        # Create a node for the topic
                        session.run("MERGE (p:Topic {name: $topic})", topic=topic)

                        # Create relationships between subject, theme, and topic nodes
                        session.run(
                            """
                            MATCH (s:Subject {name: $subject})
                            MATCH (t:Theme {name: $theme})
                            MATCH (p:Topic {name: $topic})
                            MERGE (s)-[:HAS_THEME]->(t)
                            MERGE (t)-[:HAS_TOPIC]->(p)
                            """,
                            subject=subject, theme=theme_name, topic=topic
                        )
