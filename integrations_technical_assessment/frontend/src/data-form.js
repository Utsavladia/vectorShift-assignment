import { useState } from 'react';
import {
    Box,
    TextField,
    Button,
    Typography,
    List,
    ListItem,
    ListItemText,
    Divider,
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    'Notion': 'notion',
    'Airtable': 'airtable',
    'HubSpot': 'hubspot'
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const endpoint = endpointMapping[integrationType];

    const handleLoad = async () => {
        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));
            const response = await axios.post(`http://localhost:8000/integrations/${endpoint}/load`, formData);
            const data = response.data;
            setLoadedData(data);
        } catch (e) {
            alert(e?.response?.data?.detail);
        }
    }

    const formatDate = (dateString) => {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleString();
    }

    const renderItem = (item) => (
        <ListItem key={item.id} alignItems="flex-start">
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
                                <a href={item.url} target="_blank" rel="noopener noreferrer">
                                    View in HubSpot
                                </a>
                            </Typography>
                        )}
                    </Box>
                }
            />
        </ListItem>
    );

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' width='100%'>
            <Box display='flex' flexDirection='column' width='100%' maxWidth={800}>
                {loadedData ? (
                    <List>
                        {loadedData.map((item, index) => (
                            <Box key={item.id}>
                                {renderItem(item)}
                                {index < loadedData.length - 1 && <Divider />}
                            </Box>
                        ))}
                    </List>
                ) : (
                    <Typography variant="body1" align="center" sx={{ mt: 2 }}>
                        No data loaded. Click "Load Data" to fetch items.
                    </Typography>
                )}
                <Box display='flex' justifyContent='center' gap={2} sx={{ mt: 2 }}>
                    <Button
                        onClick={handleLoad}
                        variant='contained'
                    >
                        Load Data
                    </Button>
                    <Button
                        onClick={() => setLoadedData(null)}
                        variant='contained'
                        color="secondary"
                    >
                        Clear Data
                    </Button>
                </Box>
            </Box>
        </Box>
    );
}
