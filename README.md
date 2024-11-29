# IFC Service

A modern web application for viewing IFC (Industry Foundation Classes) files using WebGPU and IfcOpenShell. Features a Next.js frontend with a FastAPI backend for efficient IFC processing and visualization.

## Features

- 🚀 High-performance WebGPU rendering
- 🏗️ IFC file processing with IfcOpenShell
- 🎯 _3D navigation controls_
- 📱 Responsive design
- 🎨 _Modern UI with standard BIM views_

_Not fully working yet_

## Tech Stack

### Frontend

- Next.js 14 with App Router
- TypeScript
- WebGPU for hardware-accelerated rendering
- Tailwind CSS for styling

### Backend

- FastAPI
- IfcOpenShell for IFC processing
- NumPy for geometry calculations
- Python 3.10+

## Prerequisites

- Node.js 18+
- Python 3.10+
- A WebGPU-capable browser (Chrome/Edge Canary with appropriate flags)
- Git

## Installation

1. Clone the repository:

```bash
git clone https://github.com/louistrue/ifc-webgpu.git
cd ifc-webgpu
```

2. Install frontend dependencies:

```bash
npm install
```

3. Set up the Python backend:

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```

## Development

1. Start the backend server:

```bash
cd backend
uvicorn app:app --reload
```

2. Start the frontend development server:

```bash
npm run dev
```

3. Open http://localhost:3000 in your browser

## Usage

### Navigation Controls (not fully working yet)

- **Left Mouse Button**: Orbit around model
- **Right/Middle Mouse Button**: Pan
- **Mouse Wheel**: Zoom in/out
- **Keyboard Shortcuts**:
  - F: Front view
  - T: Top view
  - S: Side view
  - R: Reset to default 45° view

### Features

- Upload and view IFC files
- Standard BIM viewing angles
- Real-time navigation
- High-performance rendering

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). This means:

### You are free to:

- Use the software for any purpose
- Change the software to suit your needs
- Share the software with others
- Share the changes you make

### You must:

- Make available the complete source code when you distribute the software
- Include a copy of the AGPL-3.0 license with the software
- State changes you made to the software
- Make available the complete source code of any network-delivered applications that use the software

### Additional Terms:

- This is not legal advice. For a full understanding of your rights and obligations under the AGPL-3.0, consult the full license text or a legal professional.
- The full license text can be found in the LICENSE file or at: https://www.gnu.org/licenses/agpl-3.0.html

## Acknowledgments

- [IfcOpenShell](http://ifcopenshell.org/) for IFC file processing
- [WebGPU](https://gpuweb.github.io/gpuweb/) for modern graphics rendering
- The open-source community for various tools and libraries used in this project
