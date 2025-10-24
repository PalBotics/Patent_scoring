# Patent Scoring System

A system for automatically evaluating patents related to an autonomous demining robot project. The system scores patents for relevance and categorizes them into relevant subsystems.

## Features

- FastAPI backend with SQLite storage
- API key authentication
- Keyword and LLM-based scoring options
- Local and Airtable integration modes
- Caching of scoring results
- Subsystem categorization
- Background job support (planned)

## Project Structure

- `/api`: FastAPI application
  - `main.py`: Main API endpoints
  - `schemas.py`: Pydantic models
  - `test_api.py`: API tests
- `/db.py`: Database operations
- `/scorer.py`: Patent scoring logic
- `/airtable_client.py`: Airtable integration

## Setup

1. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate  # Windows
```

2. Install dependencies:
```bash
pip install -r api/requirements.txt
```

3. Copy `.env.example` to `.env` and fill in your API keys:
```
APP_API_KEY=your-api-key
OPENAI_API_KEY=your-openai-key
AIRTABLE_API_KEY=your-airtable-key
AIRTABLE_BASE_ID=your-base-id
AIRTABLE_TABLE_NAME=your-table-name
```

4. Run the development server:
```bash
uvicorn api.main:app --reload
```

## Testing

Run tests with pytest:
```bash
pytest -v api/test_api.py
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## License

TBD