import os

import openai
import pandas as pd
from ipware import get_client_ip
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from neo4j import GraphDatabase
from .models import Profile, UserAgentLog
from .service import get_geo_location, convert_to_dict_of_lists, run_query, save_dict_in_neo4j
import platform


@csrf_exempt
def api_handler(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        link = data.get('link')
        u_id = data.get('unique_id')
        phone = data.get('phone')
        email = data.get('email')
        # pr = Profile.objects.all()
        # pro = [p.details for p in pr]
        # print(pro)
        # Profile.objects.all().delete()
        unique_details = []
        meta_data = []
        current_directory = os.getcwd()
        data_folder_path = os.path.join(current_directory, 'data')
        file_path = f"{data_folder_path}/profile_data_{name}.json"
        profile = Profile.objects.filter(name=name).first()

        user_agent = request.META.get('HTTP_USER_AGENT', '')
        add = request.META['REMOTE_ADDR']
        r = request.META.get('HTTP_REFERER', 'Unknown')
        lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
        path = request.path
        f_path = request.get_full_path()
        host = request.get_host()
        ipv4_address = host.split(':')[0]
        # "122.173.182.127"
        geo_location_data = get_geo_location(add)
        system_platform = platform.system()
        ip, is_routable = get_client_ip(request)
        data = {
            "address": ip,
            "referer": r,
            "preferred_language": lang,
            "path": path,
            "full_path": f_path,
            "host": host,
            "user": user_agent,
            "geo_location_data": geo_location_data,
            "ipv4_address": ipv4_address,
            "platform": system_platform
        }
        details = profile.get_details_list()
        if len(details) < 1:
            profile.details = [data]
            profile.save()

        for detail in details:
            if detail != data:
                unique_details.append(detail)

        if data not in unique_details:
            unique_details.append(data)

        profile.details = unique_details
        profile.save()

        if profile is None:
            profile = Profile(name=name, link=link, u_id=u_id, details=[data])
            profile.save()
            print("name: " + profile.name)
            api_endpoint = 'https://nubela.co/proxycurl/api/v2/linkedin'
            api_key = os.environ.get('PROXY_API_KEY')
            header_dic = {'Authorization': 'Bearer ' + api_key}

            response = requests.get(api_endpoint, params={'url': link}, headers=header_dic)
            profile_data = response.json()

            with open(file_path, "w") as json_file:
                json.dump(profile_data, json_file, indent=2)
        with open(file_path, 'r') as json_file:
            json_data = json.load(json_file)
        e = [str(email), profile.email]
        details = profile.get_details_list()
        for data in details:
            json_dump = json.dumps(data, indent=2)
            meta_data.append(json_dump)
        # print(type(e))
        full_name = json_data['full_name']
        # Execute the Neo4j Cypher query
        try:
            # driver = GraphDatabase.driver(uri="neo4j+s://7054f19c.databases.neo4j.io",
            #                               auth=("neo4j", "p85x87XAhdCvO5T9G7ya84ePGuRvnJRpYqlSMKEgHzw"))
            driver = GraphDatabase.driver(uri="bolt://localhost:7687/neo4j",
                                          auth=("neo4j", "sancharika"))

            session = driver.session()

            cypher_query = f'''
                WITH $input_dict AS personData 
                MERGE (p:Person {{name: personData.full_name ,  unique_id: '{str(u_id)}'}})
SET p.occupation = personData.occupation,
    p.email = {e},
    p.phone = '{str(phone)}',
    p.follower_count = personData.follower_count,
    p.summary = personData.summary,
    p.profile_pic_url = personData.profile_pic_url,
    p.headline = personData.headline,
    p.linkedin_profile_url = 'https://www.linkedin.com/in/' + personData.public_identifier,
    p.connections = personData.connections,
    p.personal_emails = personData.personal_emails,
    p.personal_numbers = personData.personal_numbers,
    p.github_profile_id = personData.extra.github_profile_id,
    p.facebook_profile_id = personData.extra.facebook_profile_id,
    p.twitter_profile_id = personData.extra.twitter_profile_id,
    p.meta_data = {meta_data}

//demography
MERGE (demography:Demography {{name: 'Demography '+personData.full_name}})
SET
  demography.country = personData.country,
  demography.occupation = personData.occupation,
  demography.city = personData.city,
  demography.gender = personData.gender,
  demography.state = personData.state,
  demography.languages = personData.languages

MERGE (p)-[:HAS_DEMOGRAPHY]->(demography)

//biography
MERGE (bio:BIOGRAPHY {{name: 'Biography '+ personData.full_name}})
MERGE (p)-[:HAS_BIOGRAPHY]->(bio)

//Psychography
MERGE (psy:PSYCHOGRAPHY {{name: 'Psychography '+ personData.full_name}})
MERGE (p)-[:HAS_PSYCHOGRAPHY]->(psy)

//language known
FOREACH (lang IN personData.languages |
MERGE (language:LANGUAGE {{name: lang}})
MERGE (p)-[:KNOWN_LANGUAGES]->(language)
MERGE (demography)-[:USER_DEMOGRAPHY]->(language)
)


//interests known
FOREACH (interest IN personData.interests |
MERGE (interests:Interests {{name: interest}})
MERGE (p)-[:INTERESTS]->(interests)
MERGE (psy)-[:USER_PSYCHOGRAPHY]->(interests)
)

// Create nodes for each test score and link them to the person node
FOREACH (scoreData IN personData.accomplishment_test_scores |
MERGE (score:TestScore {{name: scoreData.name}})
SET score.date_on = datetime({{year: scoreData.date_on.year, month: scoreData.date_on.month, 
day: scoreData.date_on.day}}),
score.score = scoreData.score,
score.description = scoreData.description
MERGE (p)-[:ACHIEVED]->(score)
MERGE (bio)-[:USER_BIOGRAPHY]->(score)
)

//VIEWED
FOREACH (personViewData IN personData.people_also_viewed |
MERGE (pv:Person {{name: personViewData.name}})
ON CREATE SET pv.summary = personViewData.summary,
pv.city = personViewData.location,
pv.linkedin_profile_url = personViewData.link
MERGE (p)<-[:VIEWED]-(pv)
)

// Create nodes for each honor/award and link them to the person node
FOREACH (awardData IN personData.accomplishment_honors_awards |
MERGE (award:Award {{title: awardData.title}})
SET award.issued_on = datetime({{year: awardData.issued_on.year, month: awardData.issued_on.month, 
day: awardData.issued_on.day}}),
award.description = awardData.description,
award.issuer = awardData.issuer
MERGE (p)-[:RECEIVED_HONOR]->(award)
MERGE (bio)-[:USER_BIOGRAPHY]->(award)
)

// Create education nodes and relationships
FOREACH (educationData IN personData.education |
MERGE (e:Education {{school: educationData.school}})
ON CREATE SET e.logo_url = educationData.logo_url
MERGE (p)-[r:ATTENDED]->(e)
SET r.degree = educationData.degree_name,
r.grade = educationData.grade,
r.activities_and_societies = educationData.activities_and_societies,
r.description = educationData.description,
r.field_of_study = educationData.field_of_study,
r.starts_at = datetime({{year: educationData.starts_at.year, month: educationData.starts_at.month, 
day: educationData.starts_at.day}}),
r.ends_at = CASE WHEN educationData.ends_at IS NOT NULL THEN datetime({{year: educationData.ends_at.year, 
month: educationData.ends_at.month, day: educationData.ends_at.day}}) ELSE null END
MERGE (demography)-[:USER_DEMOGRAPHY]->(e)
)

// Create experiences nodes and relationships
FOREACH (experienceData IN personData.experiences |
MERGE (company:Company {{name: experienceData.company}})
ON CREATE SET company.logo_url = experienceData.logo_url,
company.company_linkedin_profile_url = experienceData.company_linkedin_profile_url
MERGE (p)-[w:WORKED_AT {{title: experienceData.title}}]->(company)
set w.description = experienceData.description,
w.starts_at = datetime({{year: experienceData.starts_at.year, month: experienceData.starts_at.month, 
day: experienceData.starts_at.day}}),
w.ends_at = CASE WHEN experienceData.ends_at IS NOT NULL THEN datetime({{year: experienceData.ends_at.year, 
month: experienceData.ends_at.month, day: experienceData.ends_at.day}}) ELSE null END
MERGE (bio)-[:USER_BIOGRAPHY]->(company)
)

// Create volunteer_work nodes and relationships
FOREACH (volunteerData IN personData.volunteer_work |
MERGE (volunteer:Volunteer {{name: volunteerData.company}})
ON CREATE SET volunteer.logo_url = volunteerData.logo_url,
volunteer.company_linkedin_profile_url = volunteerData.company_linkedin_profile_url
MERGE (p)-[v:VOLUNTEERED_AT {{title: volunteerData.title}}]->(volunteer)
set v.description = volunteerData.description,
v.cause = volunteerData.cause,
v.starts_at = datetime({{year: volunteerData.starts_at.year, 
month: volunteerData.starts_at.month, day: volunteerData.starts_at.day}}),
v.ends_at = CASE WHEN volunteerData.ends_at IS NOT NULL THEN datetime({{year: volunteerData.ends_at.year, 
month: volunteerData.ends_at.month, day: volunteerData.ends_at.day}}) ELSE null END
MERGE (psy)-[:USER_PSYCHOGRAPHY]->(volunteer)
)

// Create accomplishment_courses nodes and relationships
FOREACH (courses IN personData.accomplishment_courses |
MERGE (course:Course {{name: courses.name}})
ON CREATE SET course.number = courses.number
MERGE (p)-[:COURSES_ATTENDED]->(course)
MERGE (bio)-[:USER_BIOGRAPHY]->(course)
)

// Create accomplishment_publications nodes and relationships
FOREACH (publicationData IN personData.accomplishment_publications |
FOREACH (_ IN CASE WHEN publicationData.name IS NOT NULL THEN [1] ELSE [] END |
MERGE (publication:Publications {{name: publicationData.name}})
ON CREATE SET publication.publisher = publicationData.publisher,
publication.description = publicationData.description,
publication.url = publicationData.url,
publication.published_on = CASE WHEN publicationData.published_on IS NOT NULL THEN datetime({{
            year: publicationData.published_on.year, month: publicationData.published_on.month, 
            day: publicationData.published_on.day}}) ELSE null END
MERGE (p)-[:PUBLISHED]->(publication)
MERGE (bio)-[:USER_BIOGRAPHY]->(publication)
)
)

// Create accomplishment_patents nodes and relationships
FOREACH (patentData IN personData.accomplishment_patents |
FOREACH (_ IN CASE WHEN patentData.title IS NOT NULL THEN [1] ELSE [] END |
MERGE (patent:Patent {{name: patentData.title, patent_number:patentData.patent_number}})
ON CREATE SET patent.application_number = patentData.application_number,
patent.description = patentData.description,
patent.url = patentData.url,
patent.issuer = patentData.issuer,
patent.issued_on = CASE WHEN patentData.issued_on IS NOT NULL THEN datetime({{year: patentData.issued_on.year, 
month: patentData.issued_on.month, day: patentData.issued_on.day}}) ELSE null END
MERGE (p)-[:PATENT_ACCOMPLISHED]->(patent)
MERGE (bio)-[:USER_BIOGRAPHY]->(patent)
)
)

// Create articles nodes and relationships
FOREACH (articleData IN personData.articles |
FOREACH (_ IN CASE WHEN articleData.title IS NOT NULL THEN [1] ELSE [] END |
MERGE (article:Article {{name: articleData.title}})
ON CREATE SET article.author = articleData.author,
article.link = articleData.link,
article.image_url = articleData.image_url,
article.published_date = CASE WHEN articleData.published_date IS NOT NULL THEN datetime(
{{year: articleData.published_date.year, month: articleData.published_date.month, day: articleData.published_date.day}}) 
ELSE null END
MERGE (p)-[:ARTICLE_ACCOMPLISHED]->(article)
MERGE (bio)-[:USER_BIOGRAPHY]->(article)
)
)

// Create groups nodes and relationships
FOREACH (groupsData IN personData.groups |
FOREACH (_ IN CASE WHEN groupsData.name IS NOT NULL THEN [1] ELSE [] END |
MERGE (groups:Groups {{name: groupsData.name}})
ON CREATE SET groups.profile_pic_url = groupsData.profile_pic_url,
groups.url = groupsData.url
MERGE (p)-[:JOINED_GROUP]->(groups)
MERGE (psy)-[:USER_PSYCHOGRAPHY]->(groups)
)
)

// Certifications
FOREACH (certificationData IN personData.certifications |
MERGE (certification:Certification {{name: certificationData.name}})
SET certification.starts_at = datetime({{year: certificationData.starts_at.year, 
month: certificationData.starts_at.month, day: certificationData.starts_at.day}}),
certification.authority = certificationData.authority,
certification.ends_at = CASE WHEN certificationData.ends_at IS NOT NULL THEN datetime(
{{year: certificationData.ends_at.year, month: certificationData.ends_at.month, day: certificationData.ends_at.day}}) 
ELSE null END,
certification.display_source = certificationData.display_source,
certification.url = certificationData.url,
certification.license_number = certificationData.license_number
MERGE (p)-[:CERTIFICATION]->(certification)
MERGE (bio)-[:USER_BIOGRAPHY]->(certification)
)

// Create activity_status nodes and relationships
FOREACH (activityData IN personData.activities |
MERGE (activity:Activity {{link: activityData.link}})
SET activity.title = activityData.title
MERGE (p)-[:ACTIVITY {{status: split(activityData.activity_status, ' ')[0]}}]->(activity)
MERGE (psy)-[:USER_PSYCHOGRAPHY]->(activity)
)

// Create accomplishment_organisations nodes and relationships
FOREACH (orgData IN personData.accomplishment_organisations |
// Filter out null values for the 'name' property
FOREACH (_ IN CASE WHEN orgData.name IS NOT NULL THEN [1] ELSE [] END |
MERGE (org:Organisation {{name: orgData.name}})
ON CREATE SET org.description = orgData.description,
org.starts_at = datetime({{year: orgData.starts_at.year, month: orgData.starts_at.month, day: orgData.starts_at.day}}),
org.ends_at = CASE WHEN orgData.ends_at IS NOT NULL THEN datetime({{year: orgData.ends_at.year, 
month: orgData.ends_at.month, day: orgData.ends_at.day}}) ELSE null END
MERGE (p)-[:ORGANISATION {{title: orgData.title}}]->(org)
MERGE (psy)-[:USER_PSYCHOGRAPHY]->(org)
)
)

// Project
FOREACH (projectData IN personData.accomplishment_projects |
MERGE (project:Project {{title: projectData.title}})
SET project.description = projectData.description,
project.url = projectData.url,
project.starts_at = datetime({{year: projectData.starts_at.year, 
month: projectData.starts_at.month, day: projectData.starts_at.day}}),
project.ends_at = CASE WHEN projectData.ends_at IS NOT NULL THEN datetime({{year: projectData.ends_at.year, 
month: projectData.ends_at.month, day: projectData.ends_at.day}}) ELSE null END
MERGE (p)-[:WORKED_ON]->(project)
MERGE (bio)-[:USER_BIOGRAPHY]->(project)
)

//RECOMMENDATIONS
WITH p, personData.recommendations AS recommendations
UNWIND recommendations AS recommendation
// Extract the name and recommendation message from the recommendation string
WITH p, split(recommendation, '\n') AS recommendationLines
WITH p, trim(replace(recommendationLines[0], '"', '')) AS recommenderName,
trim(replace(recommendationLines[-1], '"', '')) AS recommendationMessage

// Create the person node (Person B - the recommender)
MERGE (personB:Person {{name: recommenderName}})

// Create the RECOMMENDED relationship from Person A to Person B with the recommendation message
MERGE (p)<-[:RECOMMENDED {{message: recommendationMessage}}]-(personB)
RETURN p
            '''
            result_dict = session.write_transaction(run_query, cypher_query, json_data)
            print(result_dict)
            # result = session.run(cypher_query)
            # print(result)
            # q = f'''match (n) return n'''
            # r = session.run(q)
            # print(r.data())

            q1 = f'''
                 MATCH (n:Person) RETURN n
                '''
            results = session.run(q1)
            data = results.data()
            q2 = f'''
                 MATCH (n:Person)-[a:ACTIVITY]->(c:Activity) RETURN c, n, a
                '''
            results2 = session.run(q2)
            data2 = results2.data()
            session.close()
        except KeyError as e:
            return JsonResponse({'error': str(e)})

        try:
            # Assuming you have retrieved the DataFrame 'df1' from the Neo4j data
            extracted_data = [d['n'] for d in data]
            df1 = pd.DataFrame(extracted_data)
            df1 = df1.fillna('')
            # Combine columns into a new "interest" column
            df1["interest"] = df1["summary"] + df1["headline"] + df1["occupation"]
            output = df1[['interest', 'name']]
            df2 = output.copy()
            activities = [data2[i]["c"]['title'] for i in range(len(data2))]
            df2["activities"] = "NaN"
            if activities:
                # activities
                index_to_update = df2[df2["name"] == full_name].index[0]

                # Update the "activities" column for the specific row
                df2.at[index_to_update, "activities"] = activities
            interests = df2[df2["name"] == full_name]["activities"].values[0]
            interests.append(df2[df2["name"] == full_name]["interest"].values[0])
            openai.api_key = os.environ.get('OPENAI_API_KEY')
            message = [{"role": "user", "content": f"""{interests}
            as per this sentence find all the categories that this user might be interested in and also show the 
            keywords based on which it is categorised in a format->
Category 1:  
Keywords 1:
Category 2:  
Keywords 2: 
and so on  
            """}]
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-0613",
                messages=message,
                temperature=1,
                max_tokens=256,
                top_p=1,
                frequency_penalty=0,
                presence_penalty=0
            )
            keywords_string = response.choices[0].message['content']
            keywords_list = keywords_string.split('\n')
            print(keywords_list)
            result_dict = convert_to_dict_of_lists(keywords_list)
            return JsonResponse({"interested_categories": result_dict})

        except KeyError as e:
            print("Error while processing DataFrame:", e)
            return JsonResponse({'error': str(e)})

    return JsonResponse({'error': 'Invalid request method.'})


@csrf_exempt
def my_view(request):
    data = json.loads(request.body)
    name = data.get('name')
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    add = request.META['REMOTE_ADDR']
    r = request.META.get('HTTP_REFERER', 'Unknown')
    lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
    # c = request.COOKIES.get('cookie_name', 'default_value')
    # ses = request.session
    path = request.path
    f_path = request.get_full_path()
    host = request.get_host()
    # session_data = json.dumps(dict(ses))
    # Extract the IPv4 address from the hostname (assuming IPv4 addresses are used)
    ipv4_address = host.split(':')[0]
    # "122.173.182.127"
    geo_location_data = get_geo_location(add)

    # Get the system platform
    system_platform = platform.system()
    ip, is_routable = get_client_ip(request)
    data = {
        "address": ip,
        "referer": r,
        "preferred_language": lang,
        # "cookie": c,
        # "session": session_data,
        "path": path,
        "full_path": f_path,
        "host": host,
        "user": user_agent,
        "geo_location_data": geo_location_data,
        "ipv4_address": ipv4_address,
        "platform": system_platform
    }
    # UserAgentLog.objects.all().delete()
    # print(data)
    # Save the user agent data to the database
    # unique_dicts = []
    # seen_json_strings = set()

    try:
        # Check if the user exists in the database
        user_log = UserAgentLog.objects.get(name=name)
        details = user_log.get_details_list()
        # print(details)
        # Check if the details are different, update if necessary
        unique_details = []

        for detail in details:
            if detail != data:
                unique_details.append(detail)

        if data not in unique_details:
            unique_details.append(data)

        user_log.details = unique_details
        user_log.save()
        details = user_log.get_details_list()

    except UserAgentLog.DoesNotExist:
        user_log = UserAgentLog.objects.create(
            name=name,
            details=[data]
        )
        details = user_log.get_details_list()

    # user = UserAgentLog.objects.all()
    # u = [{"time": us.timestamp,
    #       "user": us.user_agent} for us in user]
    # print(u)

    return JsonResponse({"message": "Hello, user!",
                         "details": details})


@csrf_exempt
def linkedin_profile(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        linkedin_link = "https://in.linkedin.com/in/"
        # current_directory = os.getcwd()
        # data_folder_path = os.path.join(current_directory, 'data')
        # file_path = f"{data_folder_path}/profile_{name}.json"
        # param = {'country': 'IN',
        #          'first_name': f'{name}?',
        #          }
        # api_endpoint = 'https://nubela.co/proxycurl/api/search/person/'
        # api_key = os.environ.get('PROXY_API_KEY')
        # header_dic = {'Authorization': 'Bearer ' + api_key}
        # a = 1
        # if a>0:
        #     response = requests.get(api_endpoint, params=param, headers=header_dic)
        #     profile_data = response.json()
        #
        #     with open(file_path, "w") as json_file:
        #         json.dump(profile_data, json_file, indent=2)
        # with open(file_path, 'r') as json_file:
        #     json_data = json.load(json_file)
        # print(json_data)

        name_parts = name.split()
        usernames = [name.replace(" ", "").lower()]  # Initial username
        name_parts.append(name_parts[-1] + name_parts[0])
        name_parts.append(name_parts[1] + "-" + name_parts[0])
        name_parts.append(name_parts[0] + "-" + name_parts[1])
        for part in name_parts:
            usernames.append(part.lower())  # Name parts as usernames

            # Check for uniqueness and add a number if necessary
        final_usernames = []
        for username in usernames:
            count = 0
            if count == 0:
                final_usernames.append(username)
            else:
                final_usernames.append(f"{username}{count}")
        linkedin_usernames = [linkedin_link + username for username in final_usernames]

        return JsonResponse({'Possible Profile Links': linkedin_usernames})


@csrf_exempt
def cdn(request):
    # Define the lists of topics, subjects, and themes
    data = json.loads(request.body)
    interest = data.get('interest')
    # topics = [key for key, values in interest["interested_categories"].items()]
    subjects = ['Education', 'Environment', 'Health', 'Wealth', 'Technology', 'Mobility', 'Governance']
    themes = ['rewire', 'renew', 'reorder']

    categorized_topics = {}

    # Iterate through subjects and themes to create the structure
    for subject in subjects:
        categorized_topics[subject] = {}
        for theme in themes:
            categorized_topics[subject][theme] = []

    # Define your specific criteria for categorizing topics
    criteria = {
        'AI/ML/DL': {'subject': 'Technology', 'theme': 'rewire'},
        'Data Science': {'subject': 'Technology', 'theme': 'renew'},
        'Career Development': {'subject': 'Education', 'theme': 'renew'},
        'Technology Evolution': {'subject': 'Technology', 'theme': 'reorder'},
        'Business and Industry Events': {'subject': 'Technology', 'theme': 'reorder'},
        'Web Services': {'subject': 'Technology', 'theme': 'rewire'},
        'LinkedIn Profile Optimization': {'subject': 'Education', 'theme': 'rewire'},
        'World Youth Skills': {'subject': 'Education', 'theme': 'reorder'},
        'IT Industry': {'subject': 'Technology', 'theme': 'renew'}
    }

    # Categorize the topics based on your criteria
    for topic, info in criteria.items():
        subject = info['subject']
        theme = info['theme']
        categorized_topics[subject][theme].append(topic)

    # Save the categorized topics in a dictionary
    result_dict = categorized_topics

    # Print the result dictionary (optional)
    print(result_dict)
    uri = "bolt://localhost:7687"
    username = "neo4j"
    password = "sancharika"
    database_name = "giggr"  # Specify the desired database name here
    save_dict_in_neo4j(uri, username, password, result_dict, database_name)
    # Create a Neo4j driver instance with the specified database
    driver = GraphDatabase.driver(uri, auth=(username, password), database=database_name)
    session = driver.session()
    q = f'''match (n) return n'''
    r = session.run(q)
    print(r.data())

    return JsonResponse({"category": result_dict})



