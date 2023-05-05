import sys
import os
import json
import requests
import yaml
import re
from urllib.parse import urlparse

import logging
from urllib.parse import urljoin
# Set up basic configuration for logging

logger = logging.getLogger('pluginspartylogger')

plugin_stubs = {}

def get_plugins_stubs ():
    return plugin_stubs

def fetch_plugin_info(plugin_location):
    response = requests.get(plugin_location)
    if response.status_code != 200:
        logger.error(f"Error fetching plugin info: {response.status_code}")
        sys.exit(1)
    return response.json()

def save_plugin_info(plugin_info, plugin_dir):
    with open(os.path.join(plugin_dir, "ai-plugin.json"), "w") as f:
        json.dump(plugin_info, f)

def fetch_and_save_yaml(api_url, plugin_dir):
    response = requests.get(api_url)
    if response.status_code != 200:
        logger.error(f"Error fetching YAML file: {response.status_code}")
        sys.exit(1)
    yaml_file = os.path.join(plugin_dir, "openapi.yaml")
    with open(yaml_file, "w") as f:
        f.write(response.text)

def create_model_instructions(plugin_location):
    plugin_info = fetch_plugin_info(plugin_location)
    api_url = plugin_info.get("api", {}).get("url")
    if not api_url:
        print("API URL is missing or invalid")
        sys.exit(1)
    
    # If the api_url is relative, use urljoin to complement the missing information
    if not api_url.startswith(('http://', 'https://')):
        api_url = urljoin(plugin_location, api_url)
    
    yaml_response = requests.get(api_url)
    if yaml_response.status_code != 200:
        print(f"Error fetching YAML file: {yaml_response.status_code}")
        sys.exit(1)
    yaml_content = yaml_response.text
    plugin_name = plugin_info.get("name_for_model", "unknown")
    plugin_description = plugin_info.get("description_for_model", "unknown")
    openapi_spec = yaml.safe_load(yaml_content)
    yaml_string = yaml.dump(openapi_spec, default_flow_style=False)
    instructions = f"""

Instructions to interact with the plugin named {plugin_name}:
To interact with the plugin use the following information.
Plugin description: {plugin_description}\n
"""+"""
To use a plugin, you will construct the plugin function call to display using the plugin name and the operationId value and Request body parameters value available in the following specification."""+f"""
---begining of openapi specification for {plugin_name}--- 
{yaml_string}
"""+"""
Make sure to respect the plugin name, operationid and make sure to use a single well formated json object as the function parameter.
the template of the  plugin function call is: {{{ pluginName.operationId({json_object}) }}}
IMPORTANT: make sure to always enclose plugin function call with triple curly braces.
This should be written on a single line. 
Replace pluginName with the  name of the plugin, operationId with the right function name.
IMPORTANT: The function parameter is a SINGLE VALID JSON object (ex : {"akey":"avalue"}) containing the required parameters.
You need to check throughfully the function and confirm the parameter is a valid JSON object
After receiving a response from the plugin, continue the conversation based on the content of the response.
IMPORTANT: When using the plugin, don't explain what you are doing simply display the command and stop, continue after the plugin response.
Understood. When using the plugin, I will simply display the command without explaining what I'm doing, and then continue the conversation after receiving the plugin response.
"""
    return instructions, plugin_info, yaml_content

def create_request_stubs(service_name, yaml_content, api_url):
    openapi_spec = yaml.safe_load(yaml_content)

    paths = openapi_spec.get('paths', {})
    servers = openapi_spec.get('servers', [])
    # If 'servers' doesn't exist, build the missing part from the api_url
    if not servers:
        parsed_url = urlparse(api_url)
        server_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        servers.append({'url': server_url})

    stubs = {
        service_name: {
            'operations': {},
            'api': {
                'url': servers[0].get('url', '')
            }
        }
    }

    for path, methods in paths.items():
        for method, operation in methods.items():
            operation_id = operation.get('operationId')
            if operation_id:
                stubs[service_name]['operations'][operation_id] = {
                    'path': path,
                    'method': method.upper(),
                    'parameters': operation.get('parameters', [])
                }
    return stubs

def save_bearer_token(plugin_info, plugin_dir):
    auth = plugin_info.get("auth")
    if auth and auth.get("type") == "user_http" and auth.get("authorization_type") == "bearer":
        bearer_file = os.path.join(plugin_dir, "bearer.secret")
        if os.path.exists(bearer_file):
            logger.info("Bearer token file already existing. Skipping")
            return
        token = input("Enter the bearer token: ")
        with open(bearer_file, "w") as f:
            f.write(token)
        logger.info("Bearer token saved successfully.")

def register_plugin(plugin_url):
    if re.match(r"^https?://[^/]+$", plugin_url):
        plugin_location = f"{plugin_url}/.well-known/ai-plugin.json"
    instructions, plugin_info, yaml_content = create_model_instructions(plugin_url)
    plugin_name = plugin_info.get("name_for_model")

    if not plugin_name:
        logger.error("Plugin name_for_model is missing or invalid")
        sys.exit(1)

    plugin_dir = os.path.join("plugins", plugin_name)
    os.makedirs(plugin_dir, exist_ok=True)

    save_plugin_info(plugin_info, plugin_dir)
    # Save the bearer token if authentication uses a bearer token
    save_bearer_token(plugin_info, plugin_dir)

    # Extract the api_url from the plugin_info dictionary
    api_url = plugin_info.get("api", {}).get("url")
    if not api_url:
        logger.error("API URL is missing or invalid")
        sys.exit(1)

# If the api_url is incomplete, use urljoin to complement the missing information
    if not api_url.startswith(('http://', 'https://')):
        api_url = urljoin(plugin_url, api_url)
    
    fetch_and_save_yaml(api_url, plugin_dir)

    # Create request stubs for the plugin
    stub=plugin_stubs.update(create_request_stubs(plugin_name, yaml_content,api_url))

    setattr(sys.modules[__name__], plugin_name, stub)
    
    logger.info(f"Plugin {plugin_name} registered successfully")
    logger.debug(f" Plugin stubs:{plugin_stubs}")
    
    # Return the created stubs
    return plugin_name, stub