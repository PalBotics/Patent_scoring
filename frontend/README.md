# Patent Scoring Frontend

React + TypeScript frontend for the Patent Scoring System.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Material-UI (MUI)** for UI components
- **React Query** for data fetching and caching
- **React Router** for navigation
- **Axios** for API calls

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Copy `.env.example` to `.env` and configure:
   ```bash
   cp .env.example .env
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open [http://localhost:3000](http://localhost:3000) in your browser

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Project Structure

```
src/
├── components/     # Reusable UI components
├── pages/          # Page components (Dashboard, RecordList, etc.)
├── services/       # API client and services
├── App.tsx         # Main app component with routing
└── main.tsx        # Entry point
```

## API Integration

The frontend connects to the FastAPI backend at `http://localhost:8000/api/v1` by default.

Configure the API URL and key in `.env`:
- `VITE_API_URL` - Backend API base URL
- `VITE_API_KEY` - API key for authentication

## Features

- ✅ Dashboard with navigation cards
- ✅ Patent records list with pagination
- ✅ Material-UI theme and components
- ✅ React Query for data fetching
- 🚧 Record details modal (coming soon)
- 🚧 Mapping editor (coming soon)
- 🚧 Bulk scoring actions (coming soon)
