# Copyright 2019-2023 Xavier Rey-Robert
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os
import json
import re
from urllib.parse import urljoin, urlparse
import logging
import requests
import yaml

# Set up basic configuration for logging

logger = logging.getLogger('pluginspartylogger')

plugin_stubs = {}

def get_plugins_stubs ():
    return plugin_stubs

def fetch_plugin_info(plugin_location):
    response = requests.get(plugin_location,timeout=10000)
    if response.status_code != 200:
        logger.error("Error fetching plugin info: %i", response.status_code)
        sys.exit(1)
    return response.json()

def save_plugin_info(plugin_info, plugin_dir):
    with open(os.path.join(plugin_dir, "ai-plugin.json"), "w", encoding="utf-8") as f:
        json.dump(plugin_info, f)

def fetch_and_save_yaml(api_url, plugin_dir):
    response = requests.get(api_url, timeout=5000)
    if response.status_code != 200:
        logger.error("Error fetching YAML file: %i", response.status_code)
        sys.exit(1)
    yaml_file = os.path.join(plugin_dir, "openapi.yaml")
    with open(yaml_file, "w", encoding="utf-8") as f:
        f.write(response.text)

def create_model_instructions(plugin_location, model_name):
    plugin_info = fetch_plugin_info(plugin_location)
    api_url = plugin_info.get("api", {}).get("url")
    if not api_url:
        logger.debug("API URL is missing or invalid")
        sys.exit(1)

    # If the api_url is relative, use urljoin to complement the missing information
    if not api_url.startswith(('http://', 'https://')):
        api_url = urljoin(plugin_location, api_url)

    yaml_response = requests.get(api_url, timeout=5000)
    if yaml_response.status_code != 200:
        logger.debug("Error fetching YAML file: %i", yaml_response.status_code)
        sys.exit(1)
    yaml_content = yaml_response.text
    plugin_name = plugin_info.get("name_for_model", "unknown")
    plugin_description = plugin_info.get("description_for_model", "unknown")
    openapi_spec = yaml.safe_load(yaml_content)
    yaml_string = yaml.dump(openapi_spec, default_flow_style=False)

    # Try to load instructions from the model-specific file
    instructions_file = f"instructions/{model_name}_plugin.txt"
    if not os.path.exists(instructions_file):
        # If the model-specific file is not found, use the generic file
        instructions_file = "instructions/generic_plugin.txt"

    # Log the name of the file being loaded
    logger.debug("Loading instructions template from file: %s", instructions_file)

    # Load instructions from the selected text file
    with open(instructions_file, "r", encoding="utf-8") as file:
        instructions_template = file.read()

    # Format the instructions using the context of the associated variables
    instructions = instructions_template.format(plugin_name=plugin_name,plugin_description=plugin_description,yaml_string=yaml_string)

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
        with open(bearer_file, "w", encoding="utf-8") as f:
            f.write(token)
        logger.info("Bearer token saved successfully.")

def register_plugin(plugin_url, model_name):
    if re.match(r"^https?://[^/]+$", plugin_url):
        plugin_location = f"{plugin_url}/.well-known/ai-plugin.json"
    instructions, plugin_info, yaml_content = create_model_instructions(plugin_url, model_name)
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

    logger.info("Plugin %s registered successfully", plugin_name)
    logger.debug(" Plugin stubs: %s", plugin_stubs)

    # Return the created stubs
    return plugin_name, stub, instructions
