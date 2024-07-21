import os
import json
from serpapi import GoogleSearch
import deepl

# BASE_DIR 설정을 수정하여 secret.json 파일 경로가 정확한지 확인
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
secret_file = os.path.join(BASE_DIR, '../secret.json')

# secret.json 파일에서 API 키를 읽어옴
with open(secret_file) as f:
    secrets = json.loads(f.read())

def get_secret(setting, secrets=secrets):
    try:
        return secrets[setting]
    except KeyError:
        error_msg = "Set the {} environment variable".format(setting)
        raise KeyError(error_msg)

# SerpAPI 키 가져오기
SERP_API_KEY = get_secret("SERP_API_KEY")
DEEPL_AUTH_KEY = get_secret("DEEPL_AUTH_KEY")

# SerpAPI에서 관광지 데이터를 가져오는 함수
def osy_serp_spot(api_key, location):
    params = {
        "engine": "google_maps",
        "q": f"popular tourist spots in {location}",
        "location": location,
        "hl": "en",
        "api_key": api_key
    }
    search = GoogleSearch(params)
    results = search.get_dict()

    if 'error' in results:
        return None

    return results

# 검색 결과를 JSON 파일로 저장하는 함수
def save_results_to_json(data, filename):
    if os.path.exists(filename):
        # 기존 파일이 있으면 기존 데이터를 로드
        with open(filename, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        # 기존 데이터에 새로운 데이터를 추가
        if "local_results" in existing_data and "local_results" in data:
            existing_data["local_results"].extend(data["local_results"])
        else:
            existing_data.update(data)
    else:
        # 기존 파일이 없으면 새로운 데이터를 사용
        existing_data = data

    # 데이터를 파일에 저장
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=4)

# 검색 결과를 포맷하는 함수
def format_response(data, name, location, start_index=0, num_results=5):
    spots = []
    
    local_results = data.get("local_results", [])
    translator = deepl.Translator(DEEPL_AUTH_KEY)
    end_index = start_index + num_results
    
    for result in local_results[start_index:end_index]:
        title = result.get("title")
        rating = result.get("rating")
        description = result.get("description")
        address = result.get("address")
        if description:
            translated_description = translator.translate_text(description, target_lang="KO").text
        else:
            translated_description = "설명이 제공되지 않습니다."
        
        if title and address:
            spots.append(f"{title} - {rating} - {address} \n {translated_description}")
    
    if not spots:
        return "더 이상 추천할 장소가 없습니다.", end_index
    
    response = f"""
🤖 안녕하세요 {name}님 
{name}(으)로 {location}로 떠나시는군요!

인생샷 찍기를 좋아하시는 {name}님을 위한 {location} 인기 관광지입니다! 방문하고 싶은 관광지가 있나요?

"""
    for idx, spot in enumerate(spots, 1):
        response += f"{idx + start_index}. {spot}\n"
    
    response += """
원하시는 장소의 번호를 입력해주세요!

이 장소가 맘에 들지 않으신다면 '다른 장소도 추천해줘'라고 입력해주세요.
아니면 원하시는 장소를 직접 알려주세요
예시) 몬세라트 수도원, 08199 Montserrat, Barcelona, 스페인, 

"""
    return response, end_index

def main():
    # 미리 지정된 사용자 이름과 위치
    user_name = "NARUTO"
    location = "Barcelona"
    
    # 특정 위치로 검색 및 결과 포맷
    data = osy_serp_spot(SERP_API_KEY, location)
    
    if data:
        # 사용자 이름을 포함한 파일 이름 생성
        filename = f"{user_name.lower()}_serpapi_results.json"
        
        # 검색 결과를 JSON 파일로 저장
        save_results_to_json(data, filename)
        
        start_index = 0
        while True:
            formatted_response, start_index = format_response(data, user_name, location, start_index)
            print(formatted_response)
            
            user_input = input("입력: ")
            if user_input.lower() == "다른 장소도 추천해줘":
                if start_index >= len(data.get("local_results", [])):
                    print("더 이상 추천할 장소가 없습니다.")
                    break
                continue
            else:
                print(f"선택한 장소: {user_input}")
                break
    else:
        print("데이터를 가져오는 데 실패했습니다. 다시 시도해주세요.")

if __name__ == "__main__":
    main()
