import openai
from serpapi import GoogleSearch
from deep_translator import GoogleTranslator
from database import MongoDB_Hostname, MongoDB_Username, MongoDB_Password, SERP_API_KEY
from pymongo import MongoClient

mongodb_url = f'mongodb://{MongoDB_Username}:{MongoDB_Password}@{MongoDB_Hostname}:27017/'
client = MongoClient(mongodb_url)
db = client['TripPass']

# 사용자의 prompt에서 serpAPI 질문용 query 생성
def queryConvert(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts the location and context from a sentence and converts it into a query for SerpAPI's Google Maps search."},
            {"role": "user", "content": f"Convert the following sentence into a query for SerpAPI: '{prompt}'. Here are some examples: 'restaurants near Eiffel Tower in Paris', 'popular tourist spots in New York', 'places to visit in Tokyo'. Please return it similar to these examples."}
        ],
        max_tokens=100
    )
    
    serpQuery = response.choices[0].message['content'].strip()
    return serpQuery

# 뽑아낸 쿼리를 이용해 serpAPI로 장소를 가져오기
def serpPlace(query, SERP_API_KEY, userId, tripId):
    params = {
        "engine": "google_maps",
        "q": query,
        "hl": "en",
        "api_key": SERP_API_KEY
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    if 'error' in results:
        return None

    if results:
        return parseSerpData(results, userId, tripId)
    else:
        print("검색어를 다시 입력하세요.")

# serpApi return 값 깔끔하게 보여주기
def parseSerpData(data, userId, tripId):
    if 'local_results' not in data:
        return []
    
    translator = GoogleTranslator(source='en', target='ko')
    parsed_results = []
    serp_collection = db['SerpData']
    
    for idx, result in enumerate(data['local_results'], 1):
        title = result.get('title')
        rating = result.get('rating')
        address = result.get('address')
        gps_coordinates = result.get('gps_coordinates', {})
        latitude = gps_coordinates.get('latitude')
        longitude = gps_coordinates.get('longitude')
        description = result.get('description', 'No description available.')
        translated_description = translator.translate(description)

        if not address or not latitude or not longitude:
            continue

        place_data = {
            "title": title,
            "rating": rating,
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "description": translated_description,
        }
        
        parsed_results.append(place_data)
        
        if 'price' in result:
            price = result.get('price')
            print(f"{idx}. 장소 이름: {title}, 별점: {rating}, 주소: {address}, 가격: {price}\n    {translated_description}\n")
        else:
            print(f"{idx}. 장소 이름: {title}, 별점: {rating}, 주소: {address}\n    {translated_description}\n")
    
    document = {
        "userId": userId,
        "tripId": tripId,
        "serpData": parsed_results
    }
    
    # update_one을 사용하여 문서가 존재하면 업데이트, 존재하지 않으면 삽입 (upsert)
    serp_collection.update_one(
        {"userId": userId, "tripId": tripId},
        {"$set": document},
        upsert=True
    )
    
    return parsed_results