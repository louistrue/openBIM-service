import pytest
from fastapi.testclient import TestClient
from app.main import app
import os
import json
from datetime import datetime

# Create output directory for test results
OUTPUT_DIR = os.path.join("tests", "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = TestClient(app)

@pytest.fixture
def test_ifc():
    """Fixture to ensure test file exists"""
    test_file = "tests/data/4_DT.ifc"
    if not os.path.exists(test_file):
        pytest.skip(f"Test file {test_file} not found")
    return test_file

def test_process_ifc(test_ifc):
    """Test processing IFC file"""
    with open(test_ifc, "rb") as f:
        response = client.post(
            "/api/ifc/process",
            files={"file": ("4_DT.ifc", f, "application/x-step")}
        )
        
    # Save all responses
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"process_ifc_results_{timestamp}.jsonl")
    
    with open(output_file, "w", encoding="utf-8") as f:
        # Check streaming response
        for line in response.iter_lines():
            data = json.loads(line)
            assert "status" in data
            if data["status"] == "complete":
                assert "elements" in data
            else:
                assert "progress" in data
            
            # Write each response line to the file
            f.write(line + "\n")
    
    print(f"Process IFC results saved to: {output_file}")

def test_split_by_storey(test_ifc):
    """Test splitting IFC by storey"""
    with open(test_ifc, "rb") as f:
        response = client.post(
            "/api/ifc/split-by-storey",
            files={"file": ("4_DT.ifc", f, "application/x-step")}
        )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    
    # Save test output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"storeys_{timestamp}.zip")
    
    with open(output_file, "wb") as f:
        f.write(response.content)
    assert os.path.exists(output_file)
    print(f"Zip file saved to: {output_file}")

def test_invalid_file():
    """Test with invalid file"""
    # Create a text file
    os.makedirs("tests/data", exist_ok=True)
    with open("tests/data/invalid.txt", "w") as f:
        f.write("This is not an IFC file")
    
    with open("tests/data/invalid.txt", "rb") as f:
        response = client.post(
            "/api/ifc/process",
            files={"file": ("invalid.txt", f, "text/plain")}
        )
    
    assert response.status_code == 400
    
    # Save error response
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_DIR, f"invalid_file_response_{timestamp}.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(response.json(), f, indent=2)
    print(f"Error response saved to: {output_file}")
    
    # Cleanup
    if os.path.exists("tests/data/invalid.txt"):
        os.remove("tests/data/invalid.txt")