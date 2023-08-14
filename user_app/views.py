import openai
import pandas as pd
from ipware import get_client_ip
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from neo4j import GraphDatabase
from .models import Profile, UserAgentLog
from .service import get_geo_location
import platform


@csrf_exempt
def api_handler(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        link = data.get('link')
        # blog_categories = data.get('category')

        # Save the name and link to the database
        pr = Profile.objects.all()
        pro = [p.name for p in pr]
        print(pro)
        # Profile.objects.all().delete()
        file_path = f"/Users/sancharika/PycharmProjects/giggr1/data/profile_data_{name}.json"
        exist = Profile.objects.filter(name=name).first()
        if exist is None:
            profile = Profile(name=name, link=link)
            profile.save()
            print("name: " + profile.name)
            api_endpoint = 'https://nubela.co/proxycurl/api/v2/linkedin'
            api_key = 'dgeE7JPMejOZDilJvwePFQ'
            header_dic = {'Authorization': 'Bearer ' + api_key}

            response = requests.get(api_endpoint, params={'url': link}, headers=header_dic)
            profile_data = response.json()

            with open(file_path, "w") as json_file:
                json.dump(profile_data, json_file, indent=2)
        with open(file_path, 'r') as json_file:
            json_data = json.load(json_file)

        # Access the 'full_name' attribute from the JSON data
        full_name = json_data['full_name']

        # Execute the Neo4j Cypher query
        uri = "bolt://localhost:7687/giggr"
        username = "neo4j"
        password = "sancharika"

        try:
            driver = GraphDatabase.driver(uri=uri, auth=(username, password))
            session = driver.session()

            # q = f'''match (n) detach delete n'''
            # session.run(q)

            cypher_query = f'''
                WITH '{file_path}' AS url
                CALL apoc.load.json(url) YIELD value AS personData
                MERGE (p:Person {{name: personData.full_name}})
SET p.country = personData.country,
p.occupation = personData.occupation,
p.city = personData.city,
p.gender = personData.gender,
p.state = personData.state,
p.follower_count = personData.follower_count,
p.summary = personData.summary,
p.profile_pic_url = personData.profile_pic_url,
p.headline = personData.headline,
p.linkedin_profile_url = 'https://www.linkedin.com/in/' + personData.public_identifier,
p.languages = personData.languages,
p.connections = personData.connections,
p.personal_emails = personData.personal_emails,
p.personal_numbers = personData.personal_numbers,
p.github_profile_id = personData.extra.github_profile_id,
p.facebook_profile_id = personData.extra.facebook_profile_id,
p.twitter_profile_id = personData.extra.twitter_profile_id

//language known
FOREACH (lang IN personData.languages |
MERGE (language:LANGUAGE {{name: lang}})
MERGE (p)-[:KNOWN_LANGUAGES]->(language)
)

//interests known
FOREACH (interest IN personData.interests |
MERGE (interests:Interests {{name: interest}})
MERGE (p)-[:INTERESTS]->(interests)
)

// Create nodes for each test score and link them to the person node
FOREACH (scoreData IN personData.accomplishment_test_scores |
MERGE (score:TestScore {{name: scoreData.name}})
SET score.date_on = datetime({{year: scoreData.date_on.year, month: scoreData.date_on.month, 
day: scoreData.date_on.day}}),
score.score = scoreData.score,
score.description = scoreData.description
MERGE (p)-[:ACHIEVED]->(score)
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
)

// Create accomplishment_courses nodes and relationships
FOREACH (courses IN personData.accomplishment_courses |
MERGE (course:Course {{name: courses.name}})
ON CREATE SET course.number = courses.number
MERGE (p)-[:COURSES_ATTENDED]->(course)
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
MERGE (p)-[:PATENT_ACCOMPLISHED]->(patent)
)
)

// Create groups nodes and relationships
FOREACH (groupsData IN personData.groups |
FOREACH (_ IN CASE WHEN groupsData.name IS NOT NULL THEN [1] ELSE [] END |
MERGE (groups:Groups {{name: groupsData.name}})
ON CREATE SET groups.profile_pic_url = groupsData.profile_pic_url,
groups.url = groupsData.url
MERGE (p)-[:JOINED_GROUP]->(groups)
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
)

// Create activity_status nodes and relationships
FOREACH (activityData IN personData.activities |
MERGE (activity:Activity {{link: activityData.link}})
SET activity.title = activityData.title
MERGE (p)-[:ACTIVITY {{status: split(activityData.activity_status, ' ')[0]}}]->(activity)
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

            '''
            # cypher_query = cypher_query.replace('\n', '')
            session.run(cypher_query)
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
            print(data)
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
            openai.api_key = "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"
            message = [{"role": "user", "content": f"""{interests}
            as per this list find all the categories that this user might be interested in based on rank
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
            lines = keywords_string.split('\n')
            try:
                lines = [line.strip() for line in lines if line.strip()]
            except Exception as e:
                str(e)
                lines = [keyword.strip().lstrip('- ') for keyword in lines if keyword.strip()]

            print(lines)
            # Extract keywords from lines excluding the serial numbers
            keywords = [line.split('. ')[1] for line in lines[2:]]
            return JsonResponse({"interested_categories": list(set(keywords))})

        except KeyError as e:
            print("Error while processing DataFrame:", e)
            return JsonResponse({'error': str(e)})

    return JsonResponse({'error': 'Invalid request method.'})


def my_view(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    # Save the user agent data to the database
    us = UserAgentLog.objects.filter(user_agent=user_agent).first()
    add = request.META['REMOTE_ADDR']
    r = request.META.get('HTTP_REFERER', 'Unknown')
    lang = request.META.get('HTTP_ACCEPT_LANGUAGE', 'en')
    c = request.COOKIES.get('cookie_name', 'default_value')
    ses = request.session
    path = request.path
    f_path = request.get_full_path()
    host = request.get_host()
    session_data = json.dumps(dict(ses))
    # Extract the IPv4 address from the hostname (assuming IPv4 addresses are used)
    ipv4_address = host.split(':')[0]
    geo_location_data = get_geo_location("122.173.182.127")

    # Get the system platform
    system_platform = platform.system()

    print("System Platform:", system_platform)

    ip, is_routable = get_client_ip(request)
    print(ip, is_routable)
    data = {
        "address": add,
        "referer": r,
        "preferred_language": lang,
        "cookie": c,
        "session": session_data,
        "path": path,
        "full_path": f_path,
        "host": host,
        "time": us.timestamp,
        "user": us.user_agent,
        "geo_location_data": geo_location_data,
        "ipv4_address": ipv4_address,
        "platform": system_platform
    }
    print(data)
    # user = UserAgentLog.objects.all()
    # u = [{"time": us.timestamp,
    #       "user": us.user_agent} for us in user]
    # print(u)

    return JsonResponse({"message": "Hello, user!",
                         "details": data})
