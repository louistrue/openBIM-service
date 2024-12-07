# Remove existing venv if any
Remove-Item -Recurse-Force venv -ErrorAction SilentlyContinue

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install fastapi uvicorn python-multipart ifcopenshell pydantic pydantic-settings

# Install package in development mode
pip install -e .

# Install development dependencies
pip install -r requirements-dev.txt

# Run the server
python run.py