# IFC Processing API Documentation

Welcome to the IFC Processing API documentation. This API provides a comprehensive set of endpoints for processing and analyzing IFC (Industry Foundation Classes) files.

## Key Features

- 🔍 **IFC File Processing**: Process IFC files using IfcOpenShell
- 📊 **Element Extraction**: Get detailed information about building elements
- 🏢 **Model Splitting**: Split IFC files by storey
- 📏 **Unit Conversion**: Automatic conversion to consistent units
- 🔄 **Async Processing**: Support for asynchronous processing with callbacks
- 🔒 **Secure**: API key authentication and secure file handling

## Quick Start

### Authentication

All API requests require an API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-api-key" https://api.example.com/api/ifc/process
```

### Basic Usage

1. Process an IFC file:

```bash
curl -X POST https://api.example.com/api/ifc/process \
  -H "X-API-Key: your-api-key" \
  -F "file=@path/to/your/file.ifc"
```

2. Extract building elements with callback:

```bash
curl -X POST https://api.example.com/api/ifc/extract-building-elements \
  -H "X-API-Key: your-api-key" \
  -F "file=@path/to/your/file.ifc" \
  -F 'callback_config={"url": "https://your-callback-url.com/webhook", "token": "your-token"}'
```

### Async Processing with Callbacks

For large IFC files, you can use the callback functionality to process files asynchronously:

1. Submit a request with a callback URL
2. Receive immediate response with task ID
3. Get progress updates at your callback URL
4. Receive final results when processing is complete

Example callback data:

```json
{
  "status": "processing",
  "progress": 50,
  "total_elements": 1000,
  "processed_elements": 500
}
```

## API Endpoints

- `/api/ifc/process`: Basic IFC file processing
- `/api/ifc/extract-building-elements`: Extract detailed element information
- `/api/ifc/split-by-storey`: Split IFC model by building storeys
- `/api/ifc/property-values`: Extract specific property values
- `/api/ifc/elements-info`: Get element information
- `/api/ifc/geometry`: Process geometry information

See the [API Reference](api-reference.md) for detailed endpoint documentation.

## Security

We take security seriously. Learn about our security measures in the [Security Guide](security.md).

## Support

For support, please:

1. Check the [API Reference](api-reference.md)
2. Review common issues in our documentation
3. Contact support with detailed error information

## Rate Limits

- 100 requests per minute per API key
- Maximum file size: 100MB
- Callback timeout: 300 seconds
