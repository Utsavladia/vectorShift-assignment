# hubspot.py

import datetime
import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import logging

from integrations.integration_item import IntegrationItem
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HubSpot OAuth2 configuration
CLIENT_ID = 'e44bde63-5e9e-4f39-9400-2887edf5b2c6'
CLIENT_SECRET = '61d10672-160a-4efd-af71-d127c71637f0'
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'
AUTHORIZATION_URL = 'https://app.hubspot.com/oauth/authorize'
TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'

# Required scopes for HubSpot
SCOPES = [
    'crm.objects.contacts.read',
    'crm.objects.companies.read',
    'crm.objects.deals.read'
]

async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    auth_url = f'{AUTHORIZATION_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={" ".join(SCOPES)}&state={encoded_state}'
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', json.dumps(state_data), expire=600)
    return auth_url

async def oauth2callback_hubspot(request: Request):
    if request.query_params.get('error'):
        raise HTTPException(status_code=400, detail=request.query_params.get('error_description'))
    
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))

    original_state = state_data.get('state')
    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')

    if not saved_state or original_state != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    async with httpx.AsyncClient() as client:
        response = await client.post(
            TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'redirect_uri': REDIRECT_URI,
                'code': code
            }
        )

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail='Failed to get access token')

        await delete_key_redis(f'hubspot_state:{org_id}:{user_id}')
        await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(response.json()), expire=600)

    return HTMLResponse(content="<html><script>window.close();</script></html>")

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials

def create_integration_item_metadata_object(response_json: dict, item_type: str) -> IntegrationItem:
    """Creates an integration metadata object from the HubSpot response"""
    properties = response_json.get('properties', {})
    
    # Handle different types of names based on item type
    name = 'Unnamed'
    if item_type == 'Contact':
        firstname = properties.get('firstname', '')
        lastname = properties.get('lastname', '')
        email = properties.get('email', '')
        name = f"{firstname} {lastname}".strip() or email or 'Unnamed Contact'
    elif item_type == 'Company':
        name = properties.get('name', 'Unnamed Company')
    elif item_type == 'Deal':
        name = properties.get('dealname', 'Unnamed Deal')
    
    # Convert string dates to datetime objects
    creation_time = None
    if properties.get('createdate'):
        try:
            creation_time = datetime.datetime.fromisoformat(properties['createdate'].replace('Z', '+00:00'))
        except:
            pass
            
    last_modified_time = None
    if properties.get('hs_lastmodifieddate'):
        try:
            last_modified_time = datetime.datetime.fromisoformat(properties['hs_lastmodifieddate'].replace('Z', '+00:00'))
        except:
            pass
    
    return IntegrationItem(
        id=f"{response_json.get('id', '')}_{item_type}",
        name=name,
        type=item_type,
        creation_time=creation_time,
        last_modified_time=last_modified_time,
        url=f"https://app.hubspot.com/contacts/{response_json.get('id', '')}" if item_type == 'Contact' else None
    )

async def get_items_hubspot(credentials: str, after: str = None, limit: int = 5):
    """Get items from HubSpot with pagination support."""
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    
    if not access_token:
        raise HTTPException(status_code=400, detail='Invalid access token')
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Parse the after token if it exists
    after_tokens = {}
    if after:
        try:
            after_tokens = json.loads(after)
        except:
            after_tokens = {}
    
    async def fetch_hubspot_items(url: str, item_type: str, after_token: str = None) -> dict:
        try:
            # Define properties to fetch based on item type
            properties = ['createdate', 'hs_lastmodifieddate']
            if item_type == 'Contact':
                properties.extend(['firstname', 'lastname', 'email'])
            elif item_type == 'Company':
                properties.extend(['name'])
            elif item_type == 'Deal':
                properties.extend(['dealname'])

            params = {
                'limit': limit,
                'properties': properties
            }
            if after_token:
                params['after'] = after_token

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, headers=headers)
                
                if response.status_code == 429:  # Rate limit
                    retry_after = int(response.headers.get('Retry-After', 10))
                    await asyncio.sleep(retry_after)
                    return await fetch_hubspot_items(url, item_type, after_token)
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f'Failed to fetch {item_type} data'
                    )
                
                data = response.json()
                items = [
                    create_integration_item_metadata_object(item, item_type)
                    for item in data.get('results', [])
                ]
                
                paging = data.get('paging', {})
                next_after = paging.get('next', {}).get('after')
                
                return {
                    'items': items,
                    'next_after': next_after,
                    'has_more': bool(next_after)
                }
                
        except Exception as e:
            logger.error(f"Error fetching {item_type}: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    # Fetch data for each type
    contacts_result = await fetch_hubspot_items(
        'https://api.hubapi.com/crm/v3/objects/contacts',
        'Contact',
        after_tokens.get('contacts')
    )
    
    companies_result = await fetch_hubspot_items(
        'https://api.hubapi.com/crm/v3/objects/companies',
        'Company',
        after_tokens.get('companies')
    )
    
    deals_result = await fetch_hubspot_items(
        'https://api.hubapi.com/crm/v3/objects/deals',
        'Deal',
        after_tokens.get('deals')
    )
    
    # Combine and sort all items
    all_items = (
        contacts_result['items'] +
        companies_result['items'] +
        deals_result['items']
    )
    all_items.sort(key=lambda x: x.creation_time if x.creation_time else datetime.min, reverse=True)
    
    # Create new after tokens object
    next_after_tokens = {
        'contacts': contacts_result['next_after'],
        'companies': companies_result['next_after'],
        'deals': deals_result['next_after']
    }
    
    return {
        'items': all_items[:limit],
        'next_after': json.dumps(next_after_tokens) if any(next_after_tokens.values()) else None,
        'has_more': any([
            contacts_result['has_more'],
            companies_result['has_more'],
            deals_result['has_more'],
            len(all_items) > limit
        ])
    }