py -m venv venv
venv\Scripts\activate
pip install "mcp[cli]", google-genai, fastapi, pytest

#debugear el server en inspector
mcp dev server.py (cambias a https:localhost:8000 al usar http)