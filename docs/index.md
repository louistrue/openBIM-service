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

## Quick Start

1. Install the package:

```bash
pip install -r requirements.txt
```

2. Set up your API key in `.env`:

```bash
API_KEY=your-api-key-here
```

3. Start the server:

```bash
python run.py
```

For more detailed information, check out:

- [API Reference](api-reference.md) for endpoint documentation
- [Security](security.md) for data privacy information
