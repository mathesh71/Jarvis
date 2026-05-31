import google.generativeai as genai

# Configure with your Gemini API key
genai.configure(api_key="AIzaSyC1VlG8X9ZxXJNZFMMTM1r2cVLzaFUCijc")

# List all available models
for m in genai.list_models():
    print(m.name)
