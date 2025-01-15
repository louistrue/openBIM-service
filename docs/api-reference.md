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

## Extract Building Elements

`POST /api/ifc/extract-building-elements`

Extracts comprehensive information about building elements including properties, quantities, materials, and their relationships.

### Features

- Paginated results for large models
- Optional filtering by IFC classes
- Consistent unit system (metric)
- Complete material layering information
- Accurate quantity calculations
- Common property extraction
- Asynchronous processing with callbacks

### Request

#### Headers

- `X-API-Key`: Your API key (required)
- `Accept`: `application/json`

#### Parameters

| Name                        | Type          | Required | Description                                 |
| --------------------------- | ------------- | -------- | ------------------------------------------- |
| file                        | File          | Yes      | IFC file to process                         |
| page                        | Integer       | No       | Page number (default: 1)                    |
| page_size                   | Integer       | No       | Items per page (default: 50, max: 10000)    |
| filtered_classes            | Array[String] | No       | List of IFC classes to include              |
| exclude_properties          | Boolean       | No       | Exclude element properties                  |
| exclude_quantities          | Boolean       | No       | Exclude quantities                          |
| exclude_materials           | Boolean       | No       | Exclude material information                |
| exclude_width               | Boolean       | No       | Exclude material widths                     |
| exclude_constituent_volumes | Boolean       | No       | Exclude constituent volumes                 |
| callback_config             | Object        | No       | Callback configuration for async processing |

#### Callback Configuration

```json
{
  "url": "https://your-callback-url.com/webhook",
  "token": "your-callback-token"
}
```

When callback_config is provided:

1. The endpoint returns immediately with a task ID
2. Progress updates (every 10%) are sent to the callback URL
3. Final results are sent to the callback URL
4. All callback requests include the provided token in the Authorization header

### Callback Data Formats

#### Progress Update

```json
{
  "status": "processing",
  "progress": 10,
  "total_elements": 100,
  "processed_elements": 10
}
```

#### Final Result

```json
{
  "status": "completed",
  "progress": 100,
  "result": {
    "metadata": {
      "total_elements": 100,
      "total_pages": 2,
      "current_page": 1,
      "page_size": 50,
      "ifc_classes": ["IfcWall", "IfcDoor"],
      "units": {
        "length": "METRE",
        "area": "SQUARE_METRE",
        "volume": "CUBIC_METRE"
      }
    },
    "elements": [
      {
        "id": "3DqaUydM99ehywE4_2hm1u",
        "ifc_class": "IfcWall",
        "object_type": "Basic Wall:Holz Aussenwand_470mm",
        "properties": {
          "loadBearing": true,
          "isExternal": true
        },
        "quantities": {
          "volume": {
            "net": 31.90906,
            "gross": 32.38024
          },
          "area": {
            "net": 68.89412,
            "gross": 68.89412
          },
          "dimensions": {
            "length": 19.684,
            "width": 0.47,
            "height": 3.5
          }
        },
        "materials": ["_Holz_wg", "_Staenderkonstruktion_ungedaemmt_wg"],
        "material_volumes": {
          "_Holz_wg": {
            "fraction": 0.04255,
            "volume": 1.35783,
            "width": 0.02
          }
        }
      }
    ]
  }
}
```

#### Error Response

```json
{
  "status": "error",
  "error": "Error message details"
}
```

### Initial Response (with callback)

```json
{
  "task_id": "12345678-1234-5678-1234-567812345678",
  "message": "Processing started. Results will be sent to callback URL."
}
```

### Error Responses

| Status Code | Description                    |
| ----------- | ------------------------------ |
| 400         | Invalid request parameters     |
| 401         | Invalid or missing API key     |
| 413         | File too large                 |
| 422         | Invalid callback configuration |
| 500         | Server error                   |

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
