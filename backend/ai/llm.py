import ollama
import json

def generate_response(prompt: str, model_name: str = "llama3"):
    """
    로컬에 설치된 Ollama를 사용하여 응답을 생성합니다.
    """
    try:
        response = ollama.chat(model=model_name, messages=[
            {
                'role': 'user',
                'content': prompt,
            },
        ])
        return response['message']['content']
    except Exception as e:
        return f"Ollama Error: {str(e)}\nMake sure Ollama is running locally and the '{model_name}' model is pulled."

def extract_wiki_pages(text_chunk: str, source_name: str, model_name: str = "llama3"):
    """
    주어진 텍스트에서 주요 개념을 추출하여 위키 페이지 형태의 JSON 데이터를 반환합니다.
    """
    prompt = f"""
You are an expert knowledge extractor. Analyze the following text and extract key entities, concepts, or topics to create Wiki pages.
For each key topic, provide a Title, a one-sentence Summary, a list of Tags, and the detailed Content (in Markdown format).

Source Name: {source_name}

Text:
{text_chunk}

Output strictly in JSON format as a list of objects. Do not include any other text or markdown formatting like ```json.
Example format:
[
  {{
    "title": "Topic Name",
    "summary": "A short one-sentence summary.",
    "tags": ["tag1", "tag2"],
    "content": "Detailed markdown content..."
  }}
]
"""
    try:
        response = ollama.chat(model=model_name, messages=[
            {'role': 'user', 'content': prompt}
        ], format='json')
        
        content = response['message']['content']
        return json.loads(content)
    except Exception as e:
        print(f"Extraction Error: {str(e)}")
        return []
