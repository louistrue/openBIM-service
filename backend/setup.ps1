# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install fastapi==0.109.0
pip install uvicorn==0.27.0
pip install ifcopenshell==0.7.0
pip install numpy==1.26.3
pip install pydantic==2.5.3
pip install python-multipart==0.0.6
pip install typing-extensions==4.9.0

# Start the server
uvicorn app:app --reload 