import pandas as pd
import os
import sys
from typing import Dict, Optional

# Add project root to path for logger import
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import logger

def load_config(config_path: str = 'config.csv') -> Dict[str, str]:
    """
    Reads the configuration from a CSV file and returns it as a dictionary.

    The CSV file must have two columns: 'key' and 'value'.

    Args:
        config_path: The path to the configuration CSV file.

    Returns:
        A dictionary containing the configuration settings.

    Raises:
        FileNotFoundError: If the config file is not found.
        ValueError: If the config file is invalid (e.g., missing required keys).
    """
    logger.log_debug(f"Loading configuration from: {config_path}")
    try:
        df = pd.read_csv(config_path)
        logger.log_debug(f"CSV file loaded successfully, {len(df)} rows found")
    except FileNotFoundError:
        logger.log_error(f"Configuration file not found at '{config_path}'")
        raise FileNotFoundError(f"Error: Configuration file not found at '{config_path}'")

    if 'key' not in df.columns or 'value' not in df.columns:
        logger.log_error("Invalid config file: Must contain 'key' and 'value' columns")
        raise ValueError("Invalid config file: Must contain 'key' and 'value' columns.")

    # Convert the two-column DataFrame to a dictionary
    config = pd.Series(df.value.values, index=df.key).to_dict()
    logger.log_debug(f"Configuration dictionary created with {len(config)} entries")

    # Validate required keys
    required_keys = [
        'aws_access_key_id',
        'aws_secret_access_key',
        'endpoint_url',
        'bucket_name',
        'sts_endpoint_url'
    ]

    missing_keys = [key for key in required_keys if key not in config or pd.isna(config[key])]
    if missing_keys:
        logger.log_error(f"Missing required configuration keys: {', '.join(missing_keys)}")
        raise ValueError(f"Missing required configuration keys: {', '.join(missing_keys)}")

    logger.log_debug(f"All required keys present: {', '.join(required_keys)}")

    # Handle optional mfa_serial_number
    if 'mfa_serial_number' in config and pd.isna(config['mfa_serial_number']):
        config['mfa_serial_number'] = None
        logger.log_debug("MFA serial number: Not configured")
    elif 'mfa_serial_number' in config:
        logger.log_debug(f"MFA serial number: Configured")

    # Handle optional ssl_verify_path
    if 'ssl_verify_path' in config and (pd.isna(config['ssl_verify_path']) or not str(config['ssl_verify_path']).strip()):
        config['ssl_verify_path'] = None
        logger.log_debug("SSL verify path: Not configured")
    elif 'ssl_verify_path' in config:
        logger.log_debug(f"SSL verify path: {config['ssl_verify_path']}")

    logger.log_debug("Configuration loaded and validated successfully")
    return config
