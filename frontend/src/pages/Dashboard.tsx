import { Box, Typography, Grid, Paper, Button } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { Assessment, List, Settings } from '@mui/icons-material'

export default function Dashboard() {
  const navigate = useNavigate()

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      
      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <List sx={{ fontSize: 48, mb: 2, color: 'primary.main' }} />
            <Typography variant="h6" gutterBottom>
              Patent Records
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 2 }}>
              Browse and manage patent records
            </Typography>
            <Button variant="contained" onClick={() => navigate('/records')}>
              View Records
            </Button>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Assessment sx={{ fontSize: 48, mb: 2, color: 'primary.main' }} />
            <Typography variant="h6" gutterBottom>
              Score Patents
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 2 }}>
              Evaluate patent relevance using AI
            </Typography>
            <Button variant="contained" disabled>
              Coming Soon
            </Button>
          </Paper>
        </Grid>

        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 3, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Settings sx={{ fontSize: 48, mb: 2, color: 'primary.main' }} />
            <Typography variant="h6" gutterBottom>
              Mapping Editor
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 2 }}>
              Configure keyword mappings
            </Typography>
            <Button variant="contained" disabled>
              Coming Soon
            </Button>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}
