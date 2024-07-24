import openai
import json

# 더미 함수: 실제 구현에서는 현재 날씨를 반환하는 코드를 작성해야 합니다.
def get_current_weather(location, unit="fahrenheit"):
    """Get the current weather in a given location"""
    weather_info = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"],
    }
    return json.dumps(weather_info)

def run_conversation():
    # Step 1: 사용자 메시지와 사용할 함수 목록을 정의합니다.
    messages = [{"role": "user", "content": "서울 날씨는 어때? "}]
    functions = [
        {
            "name": "get_current_weather",
            "description": "위치를 전달하면, 현재 날씨를 알려준다",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "구군시를 전달한다. ex. 서울특별시",
                    },
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                },
                "required": ["location"],
            },
        }
    ]
    
    # 최신 모델을 사용하여 응답을 생성합니다.
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        functions=functions,
        function_call="auto",  
    )
    response_message = response["choices"][0]["message"]

    # Step 2: GPT에서 함수 호출을 하라고 했는지 확인합니다.
    if response_message.get("function_call"):
        # Step 3: GPT에서 호출하라고 한 함수를 실제로 호출합니다.
        available_functions = {
            "get_current_weather": get_current_weather,
        }
        function_name = response_message["function_call"]["name"] 
        function_to_call = available_functions[function_name]
        function_args = json.loads(response_message["function_call"]["arguments"])
        function_response = function_to_call(
            location=function_args.get("location"),
            unit=function_args.get("unit"),
        )

        # Step 4: 함수 호출 결과를 GPT에게 다시 전달합니다.
        messages.append(response_message)
        messages.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        ) 
        second_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
        )
        return second_response["choices"][0]["message"]["content"]

print(run_conversation())
