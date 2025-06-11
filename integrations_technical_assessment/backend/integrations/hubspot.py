# hubspot.py

import datetime
import json
import secrets
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
import base64
import hashlib
import time

import requests
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

# You'll need to replace these with your HubSpot app credentials
CLIENT_ID = 'e44bde63-5e9e-4f39-9400-2887edf5b2c6'
CLIENT_SECRET = '61d10672-160a-4efd-af71-d127c71637f0'
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'

# HubSpot OAuth2 endpoints
AUTHORIZATION_URL = 'https://app.hubspot.com/oauth/authorize'
TOKEN_URL = 'https://api.hubspot.com/oauth/v1/token'

# Required scopes for HubSpot
SCOPES = [
    'crm.objects.contacts.read',
    'crm.objects.contacts.write',
    'crm.objects.companies.read',
    'crm.objects.companies.write',
    'crm.objects.deals.read',
    'crm.objects.deals.write'
]

async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')

    # Build authorization URL
    auth_url = f'{AUTHORIZATION_URL}?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={" ".join(SCOPES)}&state={encoded_state}'

    # Store state in Redis
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

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')

    return credentials

def create_integration_item_metadata_object(response_json: dict, item_type: str, parent_id=None, parent_name=None) -> IntegrationItem:
    """Creates an integration metadata object from the HubSpot response"""
    properties = response_json.get('properties', {})
    name = properties.get('name') or properties.get('firstname') or properties.get('dealname') or 'Unnamed'
    
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
    
    integration_item_metadata = IntegrationItem(
        id=f"{response_json.get('id', '')}_{item_type}",
        name=name,
        type=item_type,
        parent_id=parent_id,
        parent_path_or_name=parent_name,
        creation_time=creation_time,
        last_modified_time=last_modified_time,
        url=f"https://app.hubspot.com/contacts/{response_json.get('id', '')}" if item_type == 'Contact' else None
    )
    return integration_item_metadata

async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """Fetches and aggregates all metadata relevant for a HubSpot integration"""
    print("Starting get_items_hubspot with credentials:", credentials)
    credentials = json.loads(credentials)
    access_token = credentials.get('access_token')
    
    if not access_token:
        print("No access token found in credentials")
        raise HTTPException(status_code=400, detail='Invalid access token')
    
    print("Access token found:", access_token[:10] + "...")
    
    list_of_integration_item_metadata = []
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    # Function to handle pagination
    def fetch_all_items(url, item_type, parent_id=None, parent_name=None):
        items = []
        after = 0
        print(f"Fetching {item_type} from {url}")
        while True:
            try:
                response = requests.get(
                    f"{url}?limit=100&after={after}",
                    headers=headers
                )
                
                print(f"Response status for {item_type}:", response.status_code)
                print(f"Response body for {item_type}:", response.text[:200])  # Print first 200 chars
                
                if response.status_code == 429:  # Rate limit
                    retry_after = int(response.headers.get('Retry-After', 10))
                    print(f"Rate limited, waiting {retry_after} seconds")
                    time.sleep(retry_after)
                    continue
                    
                if response.status_code != 200:
                    print(f"Error fetching {item_type}: {response.status_code} - {response.text}")
                    break
                    
                data = response.json()
                results = data.get('results', [])
                print(f"Found {len(results)} {item_type} items")
                
                for item in results:
                    items.append(create_integration_item_metadata_object(
                        item, 
                        item_type,
                        parent_id,
                        parent_name
                    ))
                
                if not data.get('paging', {}).get('next', {}).get('after'):
                    break
                    
                after = data['paging']['next']['after']
                
            except Exception as e:
                print(f"Error processing {item_type}: {str(e)}")
                break
                
        return items
    
    # Fetch contacts
    print("Fetching contacts...")
    contacts = fetch_all_items('https://api.hubapi.com/crm/v3/objects/contacts', 'Contact')
    print(f"Found {len(contacts)} contacts")
    list_of_integration_item_metadata.extend(contacts)
    
    # Fetch companies
    print("Fetching companies...")
    companies = fetch_all_items('https://api.hubapi.com/crm/v3/objects/companies', 'Company')
    print(f"Found {len(companies)} companies")
    list_of_integration_item_metadata.extend(companies)
    
    # Fetch deals
    print("Fetching deals...")
    deals = fetch_all_items('https://api.hubapi.com/crm/v3/objects/deals', 'Deal')
    print(f"Found {len(deals)} deals")
    list_of_integration_item_metadata.extend(deals)
    
    print(f'Total items found: {len(list_of_integration_item_metadata)}')
    
    # Convert IntegrationItem objects to dictionaries
    items_dict = []
    for item in list_of_integration_item_metadata:
        item_dict = {
            'id': item.id,
            'name': item.name,
            'type': item.type,
            'parent_id': item.parent_id,
            'parent_path_or_name': item.parent_path_or_name,
            'creation_time': item.creation_time.isoformat() if item.creation_time else None,
            'last_modified_time': item.last_modified_time.isoformat() if item.last_modified_time else None,
            'url': item.url,
            'directory': item.directory,
            'children': item.children,
            'mime_type': item.mime_type,
            'delta': item.delta,
            'drive_id': item.drive_id,
            'visibility': item.visibility
        }
        items_dict.append(item_dict)
    
    print(f'HubSpot Integration Items: {json.dumps(items_dict, indent=2)}')
    
    return list_of_integration_item_metadata