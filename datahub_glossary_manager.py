import os
import re
import time
import logging
import pandas as pd
import configparser
from typing import Dict, List, Optional

from datahub.emitter.rest_emitter import DataHubRestEmitter
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.metadata.schema_classes import (
    GlossaryNodeInfoClass,
    GlossaryTermInfoClass,
    OwnershipTypeClass,
    OwnershipClass,
    OwnerClass,
    AuditStampClass
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataHubGlossaryManager:
    def __init__(self, gms_server: str = None, token: str = None):
        """
        Initialize the DataHub Glossary Manager

        Args:
            gms_server: DataHub GMS URL (optional, will use ~/.datahubenv if not provided)
            token: DataHub API token (optional, will use ~/.datahubenv if not provided)
        """
        # Load from ~/.datahubenv if parameters are not provided
        if gms_server is None or token is None:
            config = self._load_datahub_config()
            gms_server = gms_server or config.get('gms_url')
            token = token or config.get('token')

        if not gms_server:
            raise ValueError("DataHub GMS URL is required but was not provided and not found in config")

        if not token:
            raise ValueError("DataHub API token is required but was not provided and not found in config")

        # Store these for later direct API calls
        self.gms_server = gms_server
        self.token = token

        # Use DataHub REST emitter from client library
        self.emitter = DataHubRestEmitter(gms_server=gms_server, token=token)

    def _load_datahub_config(self) -> Dict[str, str]:
        """
        Load DataHub configuration from ~/.datahubenv

        Returns:
            Dictionary containing configuration values
        """
        config = {
            'gms_url': None,
            'token': None
        }

        # Get path to config file
        config_path = os.path.expanduser("~/.datahubenv")

        if os.path.exists(config_path):
            logger.info(f"Loading DataHub configuration from {config_path}")

            try:
                # Try parsing as YAML-like format first
                current_section = None
                indentation = None
                section_data = {}

                with open(config_path, 'r') as f:
                    for line in f:
                        line_stripped = line.rstrip()
                        if not line_stripped or line_stripped.startswith('#'):
                            continue

                        # Check if this is a section line (no indentation)
                        if not line.startswith(' ') and ':' in line:
                            if current_section and section_data:
                                # Process the previous section
                                if current_section == 'gms' and 'server' in section_data:
                                    config['gms_url'] = section_data['server']
                                if current_section == 'gms' and 'token' in section_data:
                                    config['token'] = section_data['token']

                            # Start new section
                            current_section = line.split(':', 1)[0].strip()
                            section_data = {}
                            indentation = None
                        elif line.startswith(' ') and ':' in line:
                            # Key-value pair within a section
                            if indentation is None:
                                indentation = len(line) - len(line.lstrip())

                            if current_section:
                                # Part of the current section
                                if len(line) - len(line.lstrip()) == indentation:
                                    key, value = [x.strip() for x in line.strip().split(':', 1)]
                                    # Remove any inline comments
                                    if '#' in value:
                                        value = value.split('#', 1)[0].strip()
                                    section_data[key] = value

                # Process the last section if there is one
                if current_section and section_data:
                    if current_section == 'gms' and 'server' in section_data:
                        config['gms_url'] = section_data['server']
                    if current_section == 'gms' and 'token' in section_data:
                        config['token'] = section_data['token']

                # If we couldn't parse in YAML-like format, try other formats
                if not config['gms_url'] and not config['token']:
                    # Try parsing as ini file
                    parser = configparser.ConfigParser()
                    parser.read(config_path)

                    # Check for values in various sections
                    for section in parser.sections():
                        if 'gms_url' in parser[section] and not config['gms_url']:
                            config['gms_url'] = parser[section]['gms_url']
                        if 'server' in parser[section] and not config['gms_url']:
                            config['gms_url'] = parser[section]['server']
                        if 'token' in parser[section] and not config['token']:
                            config['token'] = parser[section]['token']

                        # If not found, try alternative keys
                        if 'datahub_gms_url' in parser[section] and not config['gms_url']:
                            config['gms_url'] = parser[section]['datahub_gms_url']
                        if 'datahub_token' in parser[section] and not config['token']:
                            config['token'] = parser[section]['datahub_token']

            except Exception as e:
                logger.warning(f"Error parsing config file: {str(e)}")
                # If parsing fails, try simple key=value format
                with open(config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            key = key.strip().lower()
                            value = value.strip()

                            if key in ['gms_url', 'datahub_gms_url', 'server'] and not config['gms_url']:
                                config['gms_url'] = value
                            if key in ['token', 'datahub_token'] and not config['token']:
                                config['token'] = value

            logger.info(f"Loaded config: GMS URL found: {bool(config['gms_url'])}, Token found: {bool(config['token'])}")
        else:
            logger.warning(f"Configuration file {config_path} not found")

        return config

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for URN creation"""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name.lower())

    def _make_glossary_term_group_urn(self, name: str) -> str:
        """Create a glossary term group URN from a name"""
        normalized_name = self._normalize_name(name)
        return f"urn:li:glossaryNode:{normalized_name}"

    def _make_glossary_term_urn(self, name: str) -> str:
        """Create a glossary term URN from a name"""
        normalized_name = self._normalize_name(name)
        return f"urn:li:glossaryTerm:{normalized_name}"

    def _make_tag_urn(self, name: str) -> str:
        """Create a tag URN from a name"""
        normalized_name = self._normalize_name(name)
        return f"urn:li:tag:{normalized_name}"

    def _make_user_urn(self, username: str) -> str:
        """Create a user URN from a username"""
        return f"urn:li:corpuser:{username}"

    def _create_term_group(self, term_group: str) -> str:
        """
        Create a glossary term group

        Args:
            term_group: Name of the term group

        Returns:
            URN of the term group
        """
        term_group_urn = self._make_glossary_term_group_urn(term_group)

        logger.info(f"Creating or updating term group '{term_group}'")

        # Create a glossary node info class
        glossary_node_info = GlossaryNodeInfoClass(name=term_group, definition=term_group)

        # Create a metadata change proposal wrapper
        mcpw = MetadataChangeProposalWrapper(
            entityType="glossaryNode",
            entityUrn=term_group_urn,
            changeType="UPSERT",
            aspectName="glossaryNodeInfo",
            aspect=glossary_node_info
        )

        self.emitter.emit(mcpw)

        return term_group_urn

    def _create_or_update_term(self, term: str, description: str, term_group_urn: str) -> str:
        """
        Create a new glossary term or update an existing one

        Args:
            term: The glossary term
            description: Term description
            term_group_urn: URN of the parent term group

        Returns:
            URN of the term
        """
        term_urn = self._make_glossary_term_urn(term)

        logger.info(f"Creating or updating term '{term}'")

        # Create a glossary term info class
        glossary_term_info = GlossaryTermInfoClass(
            name=term,
            definition=description,
            termSource="EXTERNAL_GLOSSARY",
            parentNode=term_group_urn
        )

        # Create a metadata change proposal wrapper
        mcpw = MetadataChangeProposalWrapper(
            entityType="glossaryTerm",
            entityUrn=term_urn,
            changeType="UPSERT",
            aspectName="glossaryTermInfo",
            aspect=glossary_term_info
        )

        self.emitter.emit(mcpw)

        return term_urn

    def _associate_owners_with_term(self, term_urn: str, owners: List[str], ownership_types: List[str]) -> None:
        """
        Associate owners with a glossary term

        Args:
            term_urn: URN of the glossary term
            owners: List of owner emails or usernames
            ownership_types: List of ownership types corresponding to each owner
        """
        logger.info(f"Associating {len(owners)} owners with term {term_urn}")

        owner_objects = []

        for i, owner in enumerate(owners):
            if not owner or pd.isna(owner):
                continue

            # Clean owner string
            owner = owner.strip()

            # For email addresses, use just the username part
            if '@' in owner:
                username = owner.split('@')[0]
            else:
                username = owner

            # Create URN for the owner
            owner_urn = self._make_user_urn(username)

            # Get the ownership type based on index
            ownership_type = ownership_types[i] if i < len(ownership_types) else "TECHNICAL_OWNER"

            # Create an Owner class
            owner_object = OwnerClass(
                owner=owner_urn,
                type=OwnershipTypeClass.TECHNICAL_OWNER if ownership_type == "TECHNICAL_OWNER" else
                OwnershipTypeClass.DATA_STEWARD if ownership_type == "DATA_STEWARD" else
                OwnershipTypeClass.BUSINESS_OWNER if ownership_type == "BUSINESS_OWNER" else
                OwnershipTypeClass.TECHNICAL_OWNER
            )
            owner_objects.append(owner_object)

        if not owner_objects:
            logger.info("No valid owners to associate")
            return

        # Create audit stamp for ownership
        current_time = int(time.time() * 1000)
        audit_stamp = AuditStampClass(
            time=current_time,
            actor="urn:li:corpuser:datahub"
        )

        # Create ownership class
        ownership = OwnershipClass(
            owners=owner_objects,
            lastModified=audit_stamp
        )

        # Create metadata change proposal
        mcpw = MetadataChangeProposalWrapper(
            entityType="glossaryTerm",
            entityUrn=term_urn,
            changeType="UPSERT",
            aspectName="ownership",
            aspect=ownership
        )

        self.emitter.emit(mcpw)

        logger.info(f"Owners associated with term successfully!")

    def _find_dataset_by_name(self, dataset_name: str) -> Optional[str]:
        """
        Find a dataset URN by searching for its name across all platforms

        Args:
            dataset_name: The full name of the dataset (table)

        Returns:
            The dataset URN if found, otherwise None
        """
        import requests
        import json

        logger.info(f"Searching for dataset by name: {dataset_name}")

        try:
            # GraphQL query to search for datasets by name
            graphql_query = """
        query searchDatasets($input: SearchInput!) {
          search(input: $input) {
            searchResults {
              entity {
                urn
                type
                ... on Dataset {
                  name
                  platform {
                    name
                  }
                  properties {
                    name
                    description
                  }
                }
              }
            }
          }
        }
        """

            # Make sure we search for the exact table name (could be qualified with db.schema)
            # Extract just the table name if it's a fully qualified name
            search_term = dataset_name.split(".")[-1] if "." in dataset_name else dataset_name

            variables = {
                "input": {
                    "type": "DATASET",
                    "query": search_term,
                    "start": 0,
                    "count": 20
                }
            }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            api_url = f"{self.gms_server}/api/graphql"

            response = requests.post(
                api_url,
                headers=headers,
                json={"query": graphql_query, "variables": variables}
            )

            if response.status_code == 200:
                data = response.json()

                # Log the entire response for debugging
                logger.debug(f"Search API response: {json.dumps(data, indent=2)}")

                search_results = data.get("data", {}).get("search", {}).get("searchResults", [])

                # For fully qualified names (db.schema.table), try exact matching
                if "." in dataset_name:
                    parts = dataset_name.split(".")

                    # Could be db.schema.table or schema.table
                    for result in search_results:
                        entity = result.get("entity", {})
                        entity_name = entity.get("name", "")
                        entity_urn = entity.get("urn", "")
                        platform_name = entity.get("platform", {}).get("name", "")

                        logger.info(f"Checking result: {entity_name} on {platform_name}")

                        # Try to find an exact match with the fully qualified name
                        if entity_name == dataset_name or entity_name.endswith("." + parts[-1]):
                            logger.info(f"Found exact match: {entity_name} with URN: {entity_urn}")
                            return entity_urn

                # If no match found with exact name, try approximate matching on table name
                for result in search_results:
                    entity = result.get("entity", {})
                    entity_name = entity.get("name", "")
                    entity_urn = entity.get("urn", "")

                    # Get the name part of the entity
                    if "." in entity_name:
                        entity_table = entity_name.split(".")[-1]
                    else:
                        entity_table = entity_name

                    # Check if the table part matches
                    if entity_table.lower() == search_term.lower():
                        logger.info(f"Found table match: {entity_name} with URN: {entity_urn}")
                        return entity_urn

                logger.warning(f"No matching dataset found for: {dataset_name}")
                return None
            else:
                logger.warning(f"Failed to search for dataset: {response.status_code}")
                logger.warning(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.warning(f"Error searching for dataset: {str(e)}")
            return None

    def _get_table_columns(self, dataset_urn: str) -> List[str]:
        """
        Get all columns/fields for a given dataset/table

        Args:
            dataset_urn: URN of the dataset

        Returns:
            List of column/field names that exist in the dataset
        """
        import requests

        logger.info(f"Getting columns for dataset {dataset_urn}")

        try:
            # Query to get all columns for a dataset
            graphql_query = """
            query getDatasetSchema($urn: String!) {
              dataset(urn: $urn) {
                schema {
                  fields {
                    fieldPath
                  }
                }
              }
            }
            """

            variables = {
                "urn": dataset_urn
            }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            api_url = f"{self.gms_server}/api/graphql"

            response = requests.post(
                api_url,
                headers=headers,
                json={"query": graphql_query, "variables": variables}
            )

            if response.status_code == 200:
                data = response.json()

                if data.get("errors"):
                    logger.warning(f"GraphQL errors when getting columns: {data['errors']}")
                    return []

                # Extract column names from the response
                dataset_data = data.get("data", {}).get("dataset", {})
                schema_data = dataset_data.get("schema", {})
                fields = schema_data.get("fields", [])

                # Return just the column names
                column_names = [field.get("fieldPath") for field in fields if field.get("fieldPath")]

                logger.info(f"Found {len(column_names)} columns for dataset {dataset_urn}")
                return column_names
            else:
                logger.warning(f"Failed to get columns: {response.status_code}")
                return []
        except Exception as e:
            logger.warning(f"Error getting columns: {str(e)}")
            return []

    def _resolve_table_urn(self, db_schema_table: str) -> Optional[str]:
        """
        Resolve a database.schema.table reference to a DataHub URN

        Args:
            db_schema_table: String in format "database.schema.table" or "schema.table" or "table"

        Returns:
            DataHub URN for the table if found, otherwise None
        """
        # Clean up input
        db_schema_table = db_schema_table.strip()

        # First check if this is a known table we can directly look up
        known_tables = {
            "banking.public.account_overview": "urn:li:dataset:(urn:li:dataPlatform:snowflake,banking.public.account_overview,PROD)"
        }

        # Try exact match in known tables
        if db_schema_table in known_tables:
            known_urn = known_tables[db_schema_table]
            logger.info(f"Found dataset in known tables list: {known_urn}")

            # Verify the URN actually exists AND has required properties in DataHub
            if self._check_entity_exists_with_properties(known_urn):
                logger.info(f"Verified dataset from known tables: {known_urn}")
                return known_urn
            else:
                logger.warning(f"Known table {db_schema_table} URN does not exist or lack required properties: {known_urn}")

        # Try searching for the dataset by name
        logger.info(f"Searching for dataset by name: {db_schema_table}")
        dataset_urn = self._find_dataset_by_name(db_schema_table)

        if dataset_urn:
            # Validate that the found dataset has required properties (name, platform)
            logger.info(f"Validating search result for {db_schema_table}: {dataset_urn}")
            if self._check_entity_exists_with_properties(dataset_urn):
                logger.info(f"Found dataset URN by search: {dataset_urn}")
                return dataset_urn
            else:
                logger.warning(f"Search returned URN {dataset_urn} but validation failed for {db_schema_table}")

        logger.warning(f"Could not find dataset: {db_schema_table} using any method")
        return None

    def _resolve_column_urn(self, table_urn: str, column_name: str) -> str:
        """
        Resolve a column URN from a table URN and column name

        Args:
            table_urn: DataHub URN for the table
            column_name: Name of the column

        Returns:
            DataHub URN for the column
        """
        column_urn = f"urn:li:schemaField:({table_urn},{column_name})"
        return column_urn

    def _check_entity_exists_with_properties(self, entity_urn: str) -> bool:
        """
        Check if an entity REALLY exists in DataHub AND has required properties

        Args:
            entity_urn: URN of the entity to check

        Returns:
            Boolean indicating if the entity truly exists with required properties
        """
        import requests

        logger.info(f"Checking if entity exists with properties: {entity_urn}")

        try:
            # GraphQL query to check if entity exists with required properties
            graphql_query = """
            query entityExists($urn: String!) {
              entity(urn: $urn) {
                urn
                type
                ... on Dataset {
                  name
                  platform {
                    name
                  }
                  properties {
                    name
                    description
                  }
                  schema {
                    fields {
                      fieldPath
                    }
                  }
                }
              }
            }
            """

            variables = {
                "urn": entity_urn
            }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            api_url = f"{self.gms_server}/api/graphql"

            response = requests.post(
                api_url,
                headers=headers,
                json={"query": graphql_query, "variables": variables}
            )

            if response.status_code == 200:
                data = response.json()

                # Get entity data
                entity_data = data.get("data", {}).get("entity")

                # Check if entity exists
                if not entity_data:
                    logger.warning(f"Entity {entity_urn} not found in DataHub")
                    return False

                # For dataset entities, REQUIRE platform name and entity name
                if entity_data.get("type") == "DATASET":
                    # A real dataset MUST have a platform name
                    platform = entity_data.get("platform", {})
                    has_platform = platform and platform.get("name")

                    # A real dataset MUST have a name
                    has_name = bool(entity_data.get("name"))

                    # A real dataset SHOULD have schema or properties, but not required
                    schema = entity_data.get("schema", {})
                    has_schema = schema and schema.get("fields")

                    properties = entity_data.get("properties", {})
                    has_properties = properties and properties.get("name")

                    # Consider it a real entity ONLY if it has BOTH name and platform
                    exists = has_name and has_platform

                    logger.info(f"Dataset validation: has_name={has_name}, has_platform={has_platform}")
                    logger.info(f"Entity exists with required properties: {exists}")
                    return exists

                # For other entity types, just check if it has non-null type
                exists = entity_data.get("type") is not None
                logger.info(f"Non-dataset entity exists: {exists}")
                return exists

            else:
                logger.warning(f"Failed to check if entity exists: {response.status_code}")
                return False
        except Exception as e:
            logger.warning(f"Error checking if entity exists: {str(e)}")
            return False

    def _associate_term_with_entity(self, term_urn: str, entity_urn: str) -> None:
        """
        Associate a glossary term with an entity (table or column)

        Args:
            term_urn: URN of the glossary term
            entity_urn: URN of the entity
        """
        import requests

        logger.info(f"About to associate term {term_urn} with entity {entity_urn}")

        try:
            graphql_query = """
            mutation addTermToEntity($termUrns: [String!]!, $resourceUrn: String!, $subResourceType: SubResourceType, $subResource: String) {
                addTerms(input: {
                    termUrns: $termUrns,
                    resourceUrn: $resourceUrn,
                    subResourceType: $subResourceType,
                    subResource: $subResource
                })
            }
            """

            # If this is a column/field, the resourceUrn should be the dataset
            # and we specify the field in subResource
            match = re.match(r'urn:li:schemaField:\((.*),(.*)\)', entity_urn)
            if match:
                # It's a schema field, extract dataset URN and field name
                dataset_urn = match.group(1)
                field_name = match.group(2)

                variables = {
                    "termUrns": [term_urn],
                    "resourceUrn": dataset_urn,
                    "subResourceType": "DATASET_FIELD",
                    "subResource": field_name
                }
            else:
                # Not a schema field, use the URN directly
                variables = {
                    "termUrns": [term_urn],
                    "resourceUrn": entity_urn,
                    "subResourceType": None,
                    "subResource": None
                }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            api_url = f"{self.gms_server}/api/graphql"

            # Log the full request for debugging
            logger.debug(f"GraphQL query: {graphql_query}")
            logger.info(f"Variables: {variables}")

            response = requests.post(
                api_url,
                headers=headers,
                json={"query": graphql_query, "variables": variables}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("errors"):
                    logger.warning(f"GraphQL errors: {data['errors']}")
                else:
                    logger.info(f"Term successfully associated with entity!")
            else:
                logger.warning(f"Failed to associate term with entity: {response.status_code}")
                logger.warning(f"Response: {response.text}")
        except Exception as e:
            logger.warning(f"Error associating term with entity: {str(e)}")

    def _associate_tag_with_entity(self, tag_urn: str, entity_urn: str) -> None:
        """
        Associate a tag with an entity (table or column)

        Args:
            tag_urn: URN of the tag
            entity_urn: URN of the entity
        """
        import requests

        logger.info(f"About to associate tag {tag_urn} with entity {entity_urn}")

        try:
            graphql_query = """
            mutation addTagToEntity($tagUrns: [String!]!, $resourceUrn: String!, $subResourceType: SubResourceType, $subResource: String) {
                addTags(input: {
                    tagUrns: $tagUrns,
                    resourceUrn: $resourceUrn,
                    subResourceType: $subResourceType,
                    subResource: $subResource
                })
            }
            """

            # Check if this is a schema field
            match = re.match(r'urn:li:schemaField:\((.*),(.*)\)', entity_urn)
            if match:
                # It's a schema field, extract dataset URN and field name
                dataset_urn = match.group(1)
                field_name = match.group(2)

                variables = {
                    "tagUrns": [tag_urn],
                    "resourceUrn": dataset_urn,
                    "subResourceType": "DATASET_FIELD",
                    "subResource": field_name
                }
            else:
                # Not a schema field, use the URN directly
                variables = {
                    "tagUrns": [tag_urn],
                    "resourceUrn": entity_urn,
                    "subResourceType": None,
                    "subResource": None
                }

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            }

            api_url = f"{self.gms_server}/api/graphql"

            # Log the request variables
            logger.info(f"Variables: {variables}")

            response = requests.post(
                api_url,
                headers=headers,
                json={"query": graphql_query, "variables": variables}
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("errors"):
                    logger.warning(f"GraphQL errors: {data['errors']}")
                else:
                    logger.info(f"Tag successfully associated with entity!")
            else:
                logger.warning(f"Failed to associate tag with entity: {response.status_code}")
                logger.warning(f"Response: {response.text}")
        except Exception as e:
            logger.warning(f"Error associating tag with entity: {str(e)}")

    def load_glossary_from_csv(self, csv_file_path: str) -> None:
        """
        Load glossary terms from a CSV file and upload to DataHub

        Args:
            csv_file_path: Path to the CSV file
        """
        try:
            # Read CSV file - handle Excel-exported format which may have BOM
            df = pd.read_csv(csv_file_path, encoding='utf-8-sig')

            # Map expected columns to what's in the CSV
            required_columns = [
                "Category", "Business Glossary Term", "Business Definition",
                "Technical Owner", "Data Steward", "Business Owner",
                "Tag", "Database.Schema.Table", "Field Name"
            ]

            # Check if all required columns exist
            for col in required_columns:
                if col not in df.columns:
                    logger.warning(f"Required column '{col}' not found in CSV")

            # Process each row
            for _, row in df.iterrows():
                try:
                    category = row.get("Category", "Uncategorized") if "Category" in df.columns else "Uncategorized"
                    term = row.get("Business Glossary Term", "") if "Business Glossary Term" in df.columns else ""
                    description = row.get("Business Definition", "") if "Business Definition" in df.columns else ""
                    technical_owner_str = row.get("Technical Owner", "") if "Technical Owner" in df.columns else ""
                    data_steward_str = row.get("Data Steward", "") if "Data Steward" in df.columns else ""
                    business_owner_str = row.get("Business Owner", "") if "Business Owner" in df.columns else ""
                    tags_str = row.get("Tag", "") if "Tag" in df.columns else ""
                    db_schema_table = row.get("Database.Schema.Table", "") if "Database.Schema.Table" in df.columns else ""
                    field_name = row.get("Field Name", "") if "Field Name" in df.columns else ""

                    # Skip rows where term is missing
                    if not term or pd.isna(term):
                        logger.warning("Skipping row with missing term")
                        continue

                    logger.info(f"Processing glossary term: {term} in category: {category}")

                    # Create term group if needed
                    term_group_urn = self._create_term_group(category)

                    # Create or update term
                    term_urn = self._create_or_update_term(term, description, term_group_urn)

                    # Process owners - handle multiple semicolon-separated values
                    owners = []
                    ownership_types = []

                    # Add technical owners if present
                    if technical_owner_str and not pd.isna(technical_owner_str):
                        technical_owners = [owner.strip() for owner in technical_owner_str.split(";") if owner.strip()]
                        owners.extend(technical_owners)
                        ownership_types.extend(["TECHNICAL_OWNER"] * len(technical_owners))

                    # Add data stewards if present
                    if data_steward_str and not pd.isna(data_steward_str):
                        data_stewards = [steward.strip() for steward in data_steward_str.split(";") if steward.strip()]
                        owners.extend(data_stewards)
                        ownership_types.extend(["DATA_STEWARD"] * len(data_stewards))

                    # Add business owners if present
                    if business_owner_str and not pd.isna(business_owner_str):
                        business_owners = [owner.strip() for owner in business_owner_str.split(";") if owner.strip()]
                        owners.extend(business_owners)
                        ownership_types.extend(["BUSINESS_OWNER"] * len(business_owners))

                    # Associate owners with term
                    if owners:
                        self._associate_owners_with_term(term_urn, owners, ownership_types)

                    # Process table/column association
                    if db_schema_table and not pd.isna(db_schema_table):
                        # Parse tags
                        tags = []
                        if tags_str and not pd.isna(tags_str):
                            tags = [tag.strip() for tag in tags_str.split(";") if tag.strip()]

                        # Create table URN
                        table_urn = self._resolve_table_urn(db_schema_table)

                        # Check if table exists
                        if not table_urn:
                            logger.warning(f"Table {db_schema_table} does not exist in DataHub")
                            continue

                        # If field name is provided, try to associate with column
                        if field_name and not pd.isna(field_name):
                            column_urn = self._resolve_column_urn(table_urn, field_name)
                            # Check if column exists in the table
                            column_exists = field_name in self._get_table_columns(table_urn)

                            if column_exists:
                                # Associate term with column
                                logger.info(f"Associating term {term} with column {field_name}")
                                self._associate_term_with_entity(term_urn, column_urn)

                                # Add tags to column
                                if tags:
                                    logger.info(f"Adding tags {tags} to column {field_name}")
                                    for tag in tags:
                                        tag_urn = self._make_tag_urn(tag)
                                        self._associate_tag_with_entity(tag_urn, column_urn)
                            else:
                                logger.warning(f"Column {field_name} does not exist in table {db_schema_table}")

                        # If no field name or column doesn't exist but table does
                        else:
                            # Associate term with table
                            logger.info(f"Associating term {term} with table {db_schema_table}")
                            self._associate_term_with_entity(term_urn, table_urn)

                            # Add tags to table
                            if tags:
                                logger.info(f"Adding tags {tags} to table {db_schema_table}")
                                for tag in tags:
                                    tag_urn = self._make_tag_urn(tag)
                                    self._associate_tag_with_entity(tag_urn, table_urn)

                except Exception as e:
                    logger.warning(f"Error processing row for term '{term}': {str(e)}")
                    # Continue with next row even if this one failed
                    continue

            logger.info("Glossary terms processed successfully!")

        except Exception as e:
            logger.error(f"Error processing glossary terms: {str(e)}")
            raise


# Command line interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='DataHub Glossary Manager')
    parser.add_argument('--csv-file', required=True, help='Path to CSV file with glossary terms')
    parser.add_argument('--gms-url', help='DataHub GMS URL (optional, will use ~/.datahubenv if not provided)')
    parser.add_argument('--token', help='DataHub API token (optional, will use ~/.datahubenv if not provided)')

    args = parser.parse_args()

    # Create manager and load glossary
    manager = DataHubGlossaryManager(gms_server=args.gms_url, token=args.token)
    manager.load_glossary_from_csv(args.csv_file)