# API Reference

This document provides detailed information about the available API endpoints and their usage.

## IFC Routes

### Process IFC File

`POST /api/ifc/process`

Process an IFC file and stream the results. The response is streamed as newline-delimited JSON (NDJSON).

**Request**

- Content-Type: `multipart/form-data`
- Body:
  - `file`: IFC file (required)

**Response**

- Status: 200 OK
- Content-Type: `application/x-ndjson`

Progress updates during processing:

```json
{
  "status": "processing",
  "progress": 45.5,
  "processed": 455,
  "total": 1000
}
```

Final response:

```json
{
  "status": "complete",
  "elements": [
    {
      "id": "2O2Fr$t4X7Zf8NOew3FNr2",
      "type": "IFCWALL",
      "properties": {
        "name": "Basic Wall:Interior - 165 Partition (92mm Stud):261516",
        "level": "Level 1"
      },
      "volume": 12.5,
      "area": 25.0,
      "dimensions": {
        "length": 5.0,
        "width": 0.2,
        "height": 3.0
      },
      "materials": ["Concrete", "Steel"],
      "material_volumes": {
        "Concrete": {
          "volume": 10.5,
          "fraction": 0.84
        },
        "Steel": {
          "volume": 2.0,
          "fraction": 0.16
        }
      }
    }
  ]
}
```

### Split IFC by Storey

`POST /api/ifc/split-by-storey`

Split an IFC file by building storey and return the results as a zip file.

**Request**

- Content-Type: `multipart/form-data`
- Body:
  - `file`: IFC file (required)

**Response**

- Status: 200 OK
- Content-Type: `application/zip`
- Body: ZIP file containing the split IFC files

## Authentication

All API endpoints require authentication using an API key. Include the key in the request headers:

```
X-API-Key: your-api-key-here
```

Requests without a valid API key will receive a 401 Unauthorized response.

> Note: The API documentation at `/docs` is publicly accessible, but you'll need to provide an API key to test the endpoints.

## Error Responses

All endpoints may return the following error responses:

### 400 Bad Request

```json
{
  "detail": "Error message describing the issue"
}
```

### 500 Internal Server Error

```json
{
  "detail": "Internal server error occurred"
}
```

## File Size Limits

- Maximum IFC file size: 100MB
