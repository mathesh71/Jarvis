import google.generativeai as genai

# Configure with your Gemini API key
genai.configure(api_key="paste api here")

# List all available models
for m in genai.list_models():
    print(m.name)
