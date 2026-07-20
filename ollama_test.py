import requests

OLLAMA_URL = "http://localhost:11434/"

def test_ollama_health():
    try:
        response = requests.get(OLLAMA_URL)
        if response.status_code == 200:
            print("Ollama is running!")
        else:
            print(f"Ollama responded with status code: {response.status_code}")
    except Exception as e:
        print(f"Failed to connect to Ollama: {e}")

if __name__ == "__main__":
    test_ollama_health() 