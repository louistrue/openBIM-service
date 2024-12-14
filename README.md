# IFC Processing API

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Tests](https://img.shields.io/badge/tests-pytest-green.svg)](https://docs.pytest.org/en/stable/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.2-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![IfcOpenShell](https://img.shields.io/badge/IfcOpenShell-0.8.0-orange.svg)](https://ifcopenshell.org/)

FastAPI for processing IFC (Industry Foundation Classes) using IfcOpenShell.

## Features

- 🔍 IFC file processing with IfcOpenShell
- 📊 Extract building element properties and quantities
- 🏢 Split IFC files by storey
- 📏 Automatic unit conversion
- 🏗️ Building element information including:
  - Geometry (volume, area, dimensions)
  - Materials and their volumes
  - Properties (loadBearing, isExternal)
  - Building storey assignment

## Data Privacy & Security

We take data privacy seriously:

- 🗑️ All uploaded files are automatically deleted after processing is complete
- 🧹 Temporary files are completely wiped from container storage every hour
- 🔒 Files are processed with minimal disk persistence
- 📝 Processing logs are kept only for debugging and are regularly purged
- 🔐 All API requests require authentication via API key

## Prerequisites

- Python 3.10+
- pip

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd <repository-name>
```

2. Create and activate virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\activate   # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

4. Set up your API key:

Create a `.env` file in the project root:

```bash
API_KEY=your-api-key-here
```

This API key is required for all API requests and tests.

## Development

Start the development server:

```bash
python run.py
```

The API will be available at http://localhost:8000

## Testing

Run tests using pytest:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=app tests/

# Run specific test file
pytest tests/test_endpoints.py
```

Test outputs are saved in `tests/output/` directory, including:

- Process results in JSONL format
- Error responses in JSON format

## Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── api/
│   ├── routes/
│   │   └── ifc_routes.py # API endpoints
├─ core/
│   ├── config.py        # Application settings
│   ├── security.py      # API key authentication & rate limiting
│   └── models/          # Pydantic data models
│       └── ifc.py       # IFC-related data models
└── services/
    ├── ifc/            # IFC processing services
    │   ├── properties.py  # Element property extraction
    │   ├── quantities.py  # Geometric quantities
    │   ├── splitter.py    # IFC model splitting
    │   └── units.py       # Unit conversion utilities
    └── lca/            # Life Cycle Assessment
        └── materials.py   # Material processing
tests/
├── conftest.py         # Pytest configuration
├── test_endpoints.py   # API tests
└── output/            # Test results and logs
```

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) - see the [LICENSE](LICENSE) file for details.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details on how to:

- Set up your development environment
- Follow our code style guidelines
- Submit pull requests
- Report issues

By contributing, you agree that your contributions will be licensed under the AGPL-3.0 License.

## Credits

This project is built on top of several excellent open-source projects:

- [IfcOpenShell](https://ifcopenshell.org/) - The core IFC processing library (LGPL-3.0)
- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework for building APIs (MIT)
- [Pydantic](https://docs.pydantic.dev/) - Data validation using Python type annotations (MIT)
- [pytest](https://docs.pytest.org/) - Testing framework (MIT)
- [uvicorn](https://www.uvicorn.org/) - Lightning-fast ASGI server (BSD-3-Clause)

Special thanks to:

- The IfcOpenShell community for their excellent IFC processing tools and documentation
- All contributors to the dependencies that make this project possible
