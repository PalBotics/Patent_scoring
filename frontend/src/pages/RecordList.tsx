import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  CircularProgress,
  Alert,
  TablePagination,
} from '@mui/material'
import { patentApi } from '../services/api'

export default function RecordList() {
  const [page, setPage] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(25)

  const { data, isLoading, error } = useQuery({
    queryKey: ['records', page, rowsPerPage],
    queryFn: () => patentApi.listRecords({
      limit: rowsPerPage,
      offset: page * rowsPerPage,
    }),
  })

  const handleChangePage = (_event: unknown, newPage: number) => {
    setPage(newPage)
  }

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10))
    setPage(0)
  }

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    )
  }

  if (error) {
    return (
      <Alert severity="error">
        Error loading records: {error instanceof Error ? error.message : 'Unknown error'}
      </Alert>
    )
  }

  const getRelevanceColor = (relevance?: string) => {
    switch (relevance) {
      case 'High':
        return 'success'
      case 'Medium':
        return 'warning'
      case 'Low':
        return 'error'
      default:
        return 'default'
    }
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Patent Records
      </Typography>

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Patent ID</TableCell>
              <TableCell>Title</TableCell>
              <TableCell>Relevance</TableCell>
              <TableCell>Score</TableCell>
              <TableCell>Subsystems</TableCell>
              <TableCell>Updated</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data?.records.map((record) => (
              <TableRow key={record.id} hover>
                <TableCell>{record.patent_id}</TableCell>
                <TableCell>{record.title}</TableCell>
                <TableCell>
                  {record.relevance && (
                    <Chip
                      label={record.relevance}
                      color={getRelevanceColor(record.relevance)}
                      size="small"
                    />
                  )}
                </TableCell>
                <TableCell>{record.score ?? '-'}</TableCell>
                <TableCell>
                  {record.subsystem?.map((sub) => (
                    <Chip key={sub} label={sub} size="small" sx={{ mr: 0.5 }} />
                  ))}
                </TableCell>
                <TableCell>
                  {record.updated_at
                    ? new Date(record.updated_at).toLocaleDateString()
                    : '-'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <TablePagination
        component="div"
        count={data?.total ?? 0}
        page={page}
        onPageChange={handleChangePage}
        rowsPerPage={rowsPerPage}
        onRowsPerPageChange={handleChangeRowsPerPage}
        rowsPerPageOptions={[10, 25, 50, 100]}
      />
    </Box>
  )
}
