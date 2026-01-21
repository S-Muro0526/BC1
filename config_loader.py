import os
import sys
from typing import Dict, Optional

# Add project root to path for logger import
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import logger

def load_config(config_path: str = 'config.env') -> Dict[str, str]:
    """
    Reads the configuration from an ENV file and returns it as a dictionary.

    The ENV file should have 'key=value' format.

    Args:
        config_path: The path to the configuration ENV file.

    Returns:
        A dictionary containing the configuration settings.

    Raises:
        FileNotFoundError: If the config file is not found.
        ValueError: If the config file is invalid (e.g., missing required keys).
    """
    logger.log_debug(f"Loading configuration from: {config_path}")
    config = {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
                else:
                    logger.log_warning(f"Skipping invalid line {line_num} in {config_path}: {line}")
        logger.log_debug(f"ENV file loaded successfully, {len(config)} entries found")
    except FileNotFoundError:
        logger.log_error(f"Configuration file not found at '{config_path}'")
        raise FileNotFoundError(f"Error: Configuration file not found at '{config_path}'")
    except Exception as e:
        logger.log_error(f"Error reading configuration file: {e}")
        raise

    # Validate required keys
    required_keys = [
        'aws_access_key_id',
        'aws_secret_access_key',
        'endpoint_url',
        'bucket_name',
        'sts_endpoint_url'
    ]

    missing_keys = [key for key in required_keys if key not in config or not config[key]]
    if missing_keys:
        logger.log_error(f"Missing required configuration keys: {', '.join(missing_keys)}")
        raise ValueError(f"Missing required configuration keys: {', '.join(missing_keys)}")

    logger.log_debug(f"All required keys present: {', '.join(required_keys)}")

    # Handle optional mfa_serial_number
    if 'mfa_serial_number' in config and not config['mfa_serial_number']:
        config['mfa_serial_number'] = None
        logger.log_debug("MFA serial number: Not configured")
    elif 'mfa_serial_number' in config:
        logger.log_debug(f"MFA serial number: Configured")

    # Handle optional ssl_verify_path
    if 'ssl_verify_path' in config and not str(config['ssl_verify_path']).strip():
        config['ssl_verify_path'] = None
        logger.log_debug("SSL verify path: Not configured")
    elif 'ssl_verify_path' in config:
        logger.log_debug(f"SSL verify path: {config['ssl_verify_path']}")

    logger.log_debug("Configuration loaded and validated successfully")
    return config
