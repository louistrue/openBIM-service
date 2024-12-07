# IFC Processing API

A FastAPI-based API for processing IFC (Industry Foundation Classes) files using IfcOpenShell.

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
├── core/
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
