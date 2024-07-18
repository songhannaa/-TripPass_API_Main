import requests
from deep_translator import GoogleTranslator

def getWeather(city, WEATHER_API_KEY):
    # 영어로 번역
    city = GoogleTranslator(source='ko', target='en').translate(city)
    
    api = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    
    result = requests.get(api)
    if result.status_code != 200:
        raise Exception(f"Failed to get weather data: {result.status_code} {result.text}")
    
    data = result.json()
    
    if 'weather' not in data or 'main' not in data:
        raise Exception("Invalid response from weather API")
    
    weather = data['weather'][0]['main']
    icon = data['weather'][0]['icon']
    temp = data['main']['temp']
    return weather, icon, temp