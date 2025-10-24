import { Routes, Route } from 'react-router-dom'
import { Container, AppBar, Toolbar, Typography, Box } from '@mui/material'
import Dashboard from './pages/Dashboard'
import RecordList from './pages/RecordList'

function App() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Patent Scoring System
          </Typography>
        </Toolbar>
      </AppBar>
      
      <Container maxWidth="lg" sx={{ mt: 4, mb: 4, flexGrow: 1 }}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/records" element={<RecordList />} />
        </Routes>
      </Container>
    </Box>
  )
}

export default App
