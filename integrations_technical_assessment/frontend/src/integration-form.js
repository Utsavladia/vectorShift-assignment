import { useState } from 'react';
import {
    Box,
    Autocomplete,
    TextField,
    Grid,
} from '@mui/material';
import { AirtableIntegration } from './integrations/airtable';
import { NotionIntegration } from './integrations/notion';
import { HubspotIntegration } from './integrations/hubspot';
import { DataForm } from './data-form';

const integrationMapping = {
    'Notion': NotionIntegration,
    'Airtable': AirtableIntegration,
    'HubSpot': HubspotIntegration,
};

export const IntegrationForm = () => {
    const [integrationParams, setIntegrationParams] = useState({});
    const [user, setUser] = useState('TestUser');
    const [org, setOrg] = useState('TestOrg');
    const [currType, setCurrType] = useState(null);
    const [showData, setShowData] = useState(false);
    const CurrIntegration = integrationMapping[currType];

    const handleIntegrationComplete = () => {
        setShowData(true);
    };

    return (
        <Box sx={{  px: 10, py: 6 }}>
            <Grid container spacing={2} sx={{ height: '100%', width: '100%' }}>
                {/* Left Side - Integration Form */}
                <Grid item xs={12} md={4}>
                        <Box display='flex' flexDirection='column'>
                            <TextField
                                label="User"
                                value={user}
                                onChange={(e) => setUser(e.target.value)}
                                sx={{mt: 2}}
                            />
                            <TextField
                                label="Organization"
                                value={org}
                                onChange={(e) => setOrg(e.target.value)}
                                sx={{mt: 2}}
                            />
                            <Autocomplete
                                id="integration-type"
                                options={Object.keys(integrationMapping)}
                                sx={{ width: '100%', mt: 2 }}
                                renderInput={(params) => <TextField {...params} label="Integration Type" />}
                                onChange={(e, value) => {
                                    setCurrType(value);
                                    setShowData(false);
                                }}
                            />
                        </Box>
                        {currType && 
                        <Box sx={{ mt: 2 }}>
                            <CurrIntegration 
                                user={user} 
                                org={org} 
                                integrationParams={integrationParams} 
                                setIntegrationParams={setIntegrationParams}
                                onIntegrationComplete={handleIntegrationComplete}
                            />
                        </Box>
                        }
                </Grid>

                {/* Right Side - Data Display */}
                <Grid item xs={12} md={8}>
                    {showData && integrationParams?.credentials && (
                        <DataForm 
                            integrationType={currType} 
                            credentials={integrationParams.credentials}
                            initialLoad={false}
                        />
                    )}
                </Grid>
            </Grid>
        </Box>
    );
};
