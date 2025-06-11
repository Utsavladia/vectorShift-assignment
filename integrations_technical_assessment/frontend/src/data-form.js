import { useState, useEffect } from 'react';
import {
    Box,
    TextField,
    Button,
    Typography,
    List,
    ListItem,
    ListItemText,
    Divider,
    CircularProgress,
    IconButton,
    Tooltip,
    Paper,
    Grid,
    InputAdornment,
} from '@mui/material';
import {
    Refresh as RefreshIcon,
    Clear as ClearIcon,
    Search as SearchIcon,
    FilterList as FilterIcon,
} from '@mui/icons-material';
import axios from 'axios';
import React from 'react';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'HubSpot': 'hubspot'
};

export const DataForm = ({ integrationType, credentials, initialLoad = false }) => {
    const [loadedData, setLoadedData] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [after, setAfter] = useState(null);
    const [hasMore, setHasMore] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [filteredData, setFilteredData] = useState([]);
    const [isInitialLoad, setIsInitialLoad] = useState(true);
    const [isLoadingMore, setIsLoadingMore] = useState(false);

    const ITEMS_PER_PAGE = 5;

    // Load initial data
    const handleLoad = async (isInitial = false) => {
        try {
            if (isInitial) {
                setIsLoading(true);
                setAfter(null);
                setHasMore(true);
            } else {
                setIsLoadingMore(true);
            }
            setError(null);
            
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));
            formData.append('limit', ITEMS_PER_PAGE);
            
            if (!isInitial && after) {
                formData.append('after', after);
            }
            
            const response = await axios.post(
                `http://localhost:8000/integrations/${endpointMapping[integrationType]}/load`, 
                formData
            );
            
            const { items, next_after, has_more } = response.data;
            
            if (isInitial) {
                setLoadedData(items);
            } else {
                // Check for duplicates before adding new items
                const newItems = items.filter(newItem => 
                    !loadedData.some(existingItem => existingItem.id === newItem.id)
                );
                setLoadedData(prev => [...prev, ...newItems]);
            }
            
            setAfter(next_after);
            setHasMore(has_more && items.length > 0);
            setIsInitialLoad(false);
            
        } catch (e) {
            setError(e?.response?.data?.detail || 'Failed to load data');
        } finally {
            setIsLoading(false);
            setIsLoadingMore(false);
        }
    };

    // Clear all data
    const handleClear = () => {
        setLoadedData([]);
        setAfter(null);
        setHasMore(true);
        setSearchQuery('');
        setFilteredData([]);
        setIsInitialLoad(true);
    };

    // Infinite scroll implementation
    const handleScroll = (event) => {
        const { scrollTop, clientHeight, scrollHeight } = event.currentTarget;
        if (
            scrollHeight - scrollTop <= clientHeight * 1.5 && 
            !isLoading && 
            !isLoadingMore && 
            hasMore && 
            after
        ) {
            handleLoad();
        }
    };

    // Initial load only if initialLoad prop is true
    useEffect(() => {
        if (initialLoad) {
            handleLoad(true);
        }
    }, [credentials, initialLoad]);

    // Search functionality
    useEffect(() => {
        const filtered = loadedData.filter(item => 
            item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            item.type.toLowerCase().includes(searchQuery.toLowerCase())
        );
        setFilteredData(filtered);
    }, [searchQuery, loadedData]);

    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleString();
    };

    return (
        <Box sx={{ width: '100%', maxWidth: 1200, mx: 'auto', p: 2 }}>
            {/* Header Section */}
            <Paper elevation={3} sx={{ p: 2, mb: 2 }}>
                <Grid container spacing={2} alignItems="center">
                    <Grid item xs={12} md={6}>
                        <Typography variant="h5" component="h2">
                            {integrationType} Data
                        </Typography>
                    </Grid>
                    <Grid item xs={12} md={6}>
                        <Box display="flex" gap={2} justifyContent="flex-end">
                            {isInitialLoad ? (
                                <Button
                                    variant="contained"
                                    onClick={() => handleLoad(true)}
                                    disabled={isLoading}
                                    startIcon={isLoading ? <CircularProgress size={20} /> : null}
                                >
                                    {isLoading ? 'Loading...' : 'Load Data'}
                                </Button>
                            ) : (
                                <>
                                    <TextField
                                        size="small"
                                        placeholder="Search..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        InputProps={{
                                            startAdornment: (
                                                <InputAdornment position="start">
                                                    <SearchIcon />
                                                </InputAdornment>
                                            ),
                                        }}
                                    />
                                    <Tooltip title="Refresh">
                                        <IconButton onClick={() => handleLoad(true)} disabled={isLoading}>
                                            <RefreshIcon />
                                        </IconButton>
                                    </Tooltip>
                                    <Tooltip title="Clear">
                                        <IconButton onClick={handleClear}>
                                            <ClearIcon />
                                        </IconButton>
                                    </Tooltip>
                                </>
                            )}
                        </Box>
                    </Grid>
                </Grid>
            </Paper>

            {/* Data Display Section */}
            {!isInitialLoad && (
                <Paper 
                    elevation={3} 
                    sx={{ 
                        height: 'calc(100vh - 200px)', 
                        overflow: 'auto',
                        position: 'relative'
                    }}
                    onScroll={handleScroll}
                >
                    {error && (
                        <Box sx={{ p: 2, color: 'error.main' }}>
                            {error}
                        </Box>
                    )}

                    {loadedData.length === 0 && !isLoading ? (
                        <Box 
                            display="flex" 
                            justifyContent="center" 
                            alignItems="center" 
                            height="100%"
                        >
                            <Typography color="textSecondary">
                                No data loaded. Click the refresh button to load data.
                            </Typography>
                        </Box>
                    ) : (
                        <List>
                            {(searchQuery ? filteredData : loadedData).map((item, index) => (
                                <React.Fragment key={item.id}>
                                    <ListItem 
                                        alignItems="flex-start"
                                        sx={{
                                            '&:hover': {
                                                backgroundColor: 'action.hover',
                                            },
                                        }}
                                    >
                                        <ListItemText
                                            primary={
                                                <Typography variant="h6">
                                                    {item.name} ({item.type})
                                                </Typography>
                                            }
                                            secondary={
                                                <Box>
                                                    <Typography variant="body2" color="text.secondary">
                                                        ID: {item.id}
                                                    </Typography>
                                                    <Typography variant="body2" color="text.secondary">
                                                        Created: {formatDate(item.creation_time)}
                                                    </Typography>
                                                    <Typography variant="body2" color="text.secondary">
                                                        Modified: {formatDate(item.last_modified_time)}
                                                    </Typography>
                                                    {item.url && (
                                                        <Typography variant="body2" color="text.secondary">
                                                            <a 
                                                                href={item.url} 
                                                                target="_blank" 
                                                                rel="noopener noreferrer"
                                                                style={{ color: 'primary.main' }}
                                                            >
                                                                View in {integrationType}
                                                            </a>
                                                        </Typography>
                                                    )}
                                                </Box>
                                            }
                                        />
                                    </ListItem>
                                    {index < loadedData.length - 1 && <Divider />}
                                </React.Fragment>
                            ))}
                        </List>
                    )}

                    {/* Loading Indicator */}
                    {(isLoading || isLoadingMore) && (
                        <Box 
                            display="flex" 
                            justifyContent="center" 
                            alignItems="center" 
                            p={2}
                            sx={{
                                position: 'sticky',
                                bottom: 0,
                                left: 0,
                                right: 0,
                                backgroundColor: 'background.paper',
                                borderTop: '1px solid',
                                borderColor: 'divider',
                                zIndex: 1
                            }}
                        >
                            <CircularProgress size={24} />
                        </Box>
                    )}

                    {/* End of List Message */}
                    {!hasMore && loadedData.length > 0 && (
                        <Box 
                            display="flex" 
                            justifyContent="center" 
                            alignItems="center" 
                            p={2}
                            sx={{
                                backgroundColor: 'background.paper',
                                borderTop: '1px solid',
                                borderColor: 'divider'
                            }}
                        >
                            <Typography color="textSecondary">
                                No more data to load
                            </Typography>
                        </Box>
                    )}
                </Paper>
            )}
        </Box>
    );
};
