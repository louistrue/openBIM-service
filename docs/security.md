# Security & Data Privacy

## Data Handling

We take data privacy seriously:

- 🗑️ All uploaded files are automatically deleted after processing is complete
- 🧹 Temporary files are completely wiped from container storage every hour
- 🔒 Files are processed with minimal disk persistence
- 📝 Processing logs are kept only for debugging and are regularly purged
- 🔐 All API requests require authentication via API key

## Authentication

All API endpoints require authentication using an API key. Include the key in the request headers:

```
X-API-Key: your-api-key-here
```

Requests without a valid API key will receive a 401 Unauthorized response.

## File Size Limits

- Maximum IFC file size: 100MB
