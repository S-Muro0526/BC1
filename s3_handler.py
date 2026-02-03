import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, Optional, Callable, Tuple, List, Any
import os
import sys
import datetime
import json

# Add project root to path for logger import
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import logger

def get_mfa_session_token(config: Dict[str, str], mfa_token: str) -> Dict[str, Any]:
    """
    Requests a temporary session token from STS using MFA.
    """
    logger.log_debug("Requesting STS session token with MFA")

    sts_params = {
        'aws_access_key_id': config['aws_access_key_id'],
        'aws_secret_access_key': config['aws_secret_access_key'],
        'endpoint_url': config['sts_endpoint_url'],
        'region_name': 'us-east-1'
    }

    if config.get('ssl_verify_path'):
        logger.log_debug(f"Using custom SSL certificate for STS: {config['ssl_verify_path']}")
        sts_params['verify'] = config['ssl_verify_path']

    sts_client = boto3.client('sts', **sts_params)

    token = sts_client.get_session_token(
        SerialNumber=config['mfa_serial_number'],
        TokenCode=mfa_token
    )
    logger.log_debug("STS session token obtained successfully")
    return token['Credentials']

def save_session(credentials: Dict[str, Any], filepath: str):
    """
    Saves the temporary credentials to a file in JSON format.
    """
    session_data = {
        'AccessKeyId': credentials['AccessKeyId'],
        'SecretAccessKey': credentials['SecretAccessKey'],
        'SessionToken': credentials['SessionToken'],
        'Expiration': credentials['Expiration'].isoformat() if isinstance(credentials['Expiration'], datetime.datetime) else credentials['Expiration']
    }
    with open(filepath, 'w') as f:
        json.dump(session_data, f)
    logger.log_debug(f"MFA session saved to {filepath}")

def load_session(filepath: str) -> Optional[Dict[str, Any]]:
    """
    Loads temporary credentials from a file.
    """
    if not os.path.exists(filepath):
        logger.log_debug(f"Session file not found at {filepath}")
        return None
    try:
        with open(filepath, 'r') as f:
            session_data = json.load(f)
        logger.log_debug(f"MFA session loaded from {filepath}")
        return session_data
    except Exception as e:
        logger.log_error(f"Failed to load MFA session: {e}")
        return None

def is_session_valid(session_data: Optional[Dict[str, Any]]) -> bool:
    """
    Checks if the loaded session is still valid.
    """
    if not session_data:
        return False

    expiration_str = session_data.get('Expiration')
    if not expiration_str:
        return False

    try:
        expiration = datetime.datetime.fromisoformat(expiration_str)
        # Convert to UTC if it has no timezone info, assuming STS returns UTC
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=datetime.timezone.utc)

        now = datetime.datetime.now(datetime.timezone.utc)
        # Check if expiration is at least 1 minute in the future
        return expiration > now + datetime.timedelta(minutes=1)
    except Exception as e:
        logger.log_error(f"Error validating session expiration: {e}")
        return False

def get_s3_client(config: Dict[str, str], mfa_token: Optional[str] = None, session_data: Optional[Dict[str, Any]] = None):
    """
    Establishes a session with Wasabi and returns an S3 client.
    Handles MFA authentication if mfa_serial_number and mfa_token are provided,
    or uses provided session_data.
    """
    try:
        logger.log_debug("Creating S3 client session")
        session_params = {
            "aws_access_key_id": config['aws_access_key_id'],
            "aws_secret_access_key": config['aws_secret_access_key'],
        }

        if session_data:
            logger.log_debug("Using provided session data for S3 client")
            session_params = {
                "aws_access_key_id": session_data['AccessKeyId'],
                "aws_secret_access_key": session_data['SecretAccessKey'],
                "aws_session_token": session_data['SessionToken'],
            }
        elif config.get('mfa_serial_number') and config['mfa_serial_number'] != 'YOUR_MFA_SERIAL_NUMBER_ARN (optional)':
            if not mfa_token:
                raise ValueError("MFA token is required for authentication.")

            credentials = get_mfa_session_token(config, mfa_token)
            session_params = {
                "aws_access_key_id": credentials['AccessKeyId'],
                "aws_secret_access_key": credentials['SecretAccessKey'],
                "aws_session_token": credentials['SessionToken'],
            }

        client_params = {
            'endpoint_url': config['endpoint_url'],
            **session_params
        }

        # Add custom SSL certificate if provided
        if config.get('ssl_verify_path'):
            logger.log_debug(f"Using custom SSL certificate: {config['ssl_verify_path']}")
            client_params['verify'] = config['ssl_verify_path']

        s3_client = boto3.client(
            's3',
            **client_params
        )
        logger.log_debug(f"S3 client created for endpoint: {config['endpoint_url']}")
        return s3_client
    except (NoCredentialsError, ClientError) as e:
        logger.log_error(f"Failed to create S3 client: {e}")
        raise e

def get_object_info(s3_client, bucket_name: str, source_key: str) -> Dict[str, Any]:
    """Gets metadata (like size) for a single object."""
    try:
        logger.log_debug(f"Getting object info for: {source_key}")
        head = s3_client.head_object(Bucket=bucket_name, Key=source_key)
        obj_info = {
            'Key': source_key,
            'Size': head['ContentLength'],
            'LastModified': head['LastModified']
        }
        logger.log_debug(f"Object size: {obj_info['Size']} bytes, Last Modified: {obj_info['LastModified']}")
        return obj_info
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            logger.log_error(f"Source file '{source_key}' not found in bucket '{bucket_name}'")
            raise FileNotFoundError(f"Error: Source file '{source_key}' not found in bucket '{bucket_name}'.")
        else:
            logger.log_error(f"Error getting object info: {e}")
            raise e

def list_objects_in_prefix(s3_client, bucket_name: str, source_prefix: str = '') -> Tuple[List[Dict[str, Any]], int]:
    """Lists all objects under a prefix, returning the list and their total size."""
    logger.log_debug(f"Listing objects with prefix: '{source_prefix}' in bucket: {bucket_name}")
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=source_prefix)

    objects_to_download = []
    total_size = 0
    page_count = 0
    for page in pages:
        page_count += 1
        if 'Contents' in page:
            for obj in page['Contents']:
                if obj['Size'] > 0: # Skip directories
                    objects_to_download.append(obj)
                    total_size += obj['Size']
    logger.log_debug(f"Found {len(objects_to_download)} objects across {page_count} pages, total size: {total_size} bytes")
    return objects_to_download, total_size

def list_object_versions_at_timestamp(s3_client, bucket_name: str, timestamp: datetime.datetime, source_prefix: str = '') -> Tuple[List[Dict[str, Any]], int]:
    """Finds the definitive list of object versions that existed at a given timestamp."""
    logger.log_debug(f"Listing object versions at timestamp: {timestamp} with prefix: '{source_prefix}'")
    paginator = s3_client.get_paginator('list_object_versions')
    pages = paginator.paginate(Bucket=bucket_name, Prefix=source_prefix)

    latest_valid_versions = {}
    page_count = 0
    total_entries = 0
    for page in pages:
        page_count += 1
        all_entries = page.get('Versions', []) + page.get('DeleteMarkers', [])
        total_entries += len(all_entries)
        for entry in all_entries:
            if entry['LastModified'] <= timestamp:
                key = entry['Key']
                if key not in latest_valid_versions or entry['LastModified'] > latest_valid_versions[key]['LastModified']:
                    latest_valid_versions[key] = entry

    objects_to_download = []
    total_size = 0
    for key, entry in latest_valid_versions.items():
        if 'VersionId' in entry and entry.get('Size', 0) > 0:
            objects_to_download.append(entry)
            total_size += entry['Size']

    logger.log_debug(f"Processed {total_entries} version entries across {page_count} pages")
    logger.log_debug(f"Found {len(objects_to_download)} valid versions, total size: {total_size} bytes")
    return objects_to_download, total_size

def download_file(s3_client, bucket_name: str, source_key: str, destination_path: str, callback: Optional[Callable[[int], None]] = None):
    """Downloads a single object to a specific file path."""
    logger.log_debug(f"Downloading file: {source_key} -> {destination_path}")
    os.makedirs(os.path.dirname(destination_path), exist_ok=True)
    try:
        s3_client.download_file(
            Bucket=bucket_name,
            Key=source_key,
            Filename=destination_path,
            Callback=callback
        )
        logger.log_debug(f"Successfully downloaded: {source_key}")
    except ClientError as e:
        logger.log_warning(f"Could not download {source_key}. Error: {e}")

def download_objects(
    s3_client,
    bucket_name: str,
    destination_dir: str,
    source_prefix: str,
    object_list: List[Dict[str, Any]],
    callback: Optional[Callable[[int], None]] = None
):
    """Downloads a list of objects into a destination directory."""
    logger.log_debug(f"Starting batch download of {len(object_list)} objects to: {destination_dir}")
    download_count = 0
    error_count = 0
    
    for obj in object_list:
        source_key = obj['Key']

        prefix_dir = source_prefix
        if source_prefix and not source_prefix.endswith('/'):
            prefix_dir = os.path.dirname(source_prefix.rstrip('/'))

        relative_path = os.path.relpath(source_key, start=prefix_dir if prefix_dir else '')
        destination_path = os.path.join(destination_dir, relative_path)

        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        extra_args = {}
        if 'VersionId' in obj:
            extra_args['VersionId'] = obj['VersionId']
            logger.log_debug(f"Downloading versioned object: {source_key} (Version: {obj['VersionId']})")
        else:
            logger.log_debug(f"Downloading object: {source_key}")

        try:
            s3_client.download_file(
                Bucket=bucket_name,
                Key=source_key,
                Filename=destination_path,
                ExtraArgs=extra_args if extra_args else None,
                Callback=callback
            )
            download_count += 1
        except ClientError as e:
            error_count += 1
            logger.log_warning(f"Could not download {source_key} (Version: {obj.get('VersionId', 'N/A')}). Error: {e}")
    
    logger.log_debug(f"Batch download complete: {download_count} successful, {error_count} errors")
