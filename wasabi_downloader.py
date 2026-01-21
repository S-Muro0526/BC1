import argparse
import os
import sys
import datetime
import getpass
from tqdm import tqdm
from botocore.exceptions import ClientError

# Add project root to path to allow sibling module imports
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import config_loader
import s3_handler
import logger

# --- Helper Functions ---

def get_app_root() -> str:
    """
    Returns the application root directory.
    If frozen (PyInstaller), returns the directory of the executable.
    Otherwise, returns the directory of this script.
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

def get_default_download_dir() -> str:
    """Returns the default download directory path ('./Download')."""
    return os.path.join(os.getcwd(), 'Download')

def format_bytes(byte_count: int) -> str:
    """Formats a byte count into a human-readable string."""
    if byte_count is None:
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while byte_count >= power and n < len(power_labels) -1 :
        byte_count /= power
        n += 1
    return f"{byte_count:.2f} {power_labels[n]}B"

# --- Main Logic ---

def main():
    """Main function to run the downloader."""
    # Initialize logger at the start
    logger.init_logger(mode='w')
    
    try:
        parser = argparse.ArgumentParser(description="Wasabi Hot Cloud Storage File Download Tool")
        subparsers = parser.add_subparsers(dest='command', required=True, help='Available commands')

        # --- download_file ---
        parser_file = subparsers.add_parser('download_file', help='Download a single file.')
        parser_file.add_argument('--source', required=True, help='Object key of the file to download (e.g., "path/to/file.txt").')
        parser_file.add_argument('--destination', help='Local path to save the file. Defaults to "./Download/<filename>".')

        # --- download_dir ---
        parser_dir = subparsers.add_parser('download_dir', help='Download an entire directory (prefix).')
        parser_dir.add_argument('--source', default='', help='The source directory (prefix) to download. Defaults to the entire bucket.')
        parser_dir.add_argument('--destination', help='Local directory to save files. Defaults to "./Download/".')

        # --- download_versioned ---
        parser_ver = subparsers.add_parser('download_versioned', help='Download all files from a specific point in time.')
        parser_ver.add_argument('--timestamp', required=True, help='The date for version recovery in YYYYMMDD format.')
        parser_ver.add_argument('--source', default='', help='The source directory (prefix) to download. Defaults to the entire bucket.')
        parser_ver.add_argument('--destination', help='Local directory to save files. Defaults to "./Download/".')

        # --- list_files ---
        parser_list = subparsers.add_parser('list_files', help='Recursively list files in a given prefix.')
        parser_list.add_argument('--source', default='', help='The source directory (prefix) to list. Defaults to the entire bucket.')

        # --- mfa ---
        subparsers.add_parser('mfa', help='Authenticate with MFA and save session.')

        args = parser.parse_args()
        
        logger.log_info(f"Starting command: {args.command}")
        logger.log_debug(f"Arguments: {vars(args)}")

        try:
            # 1. Load Configuration
            config_path = os.path.join(get_app_root(), 'config.env')
            logger.log_info(f"Loading configuration from: {config_path}")
            config = config_loader.load_config(config_path)
            logger.log_debug(f"Configuration loaded successfully")

            # 2. Handle MFA
            session_file = os.path.join(get_app_root(), '.mfa_session.json')
            session_data = None
            mfa_required = config.get('mfa_serial_number') and config['mfa_serial_number'] != 'YOUR_MFA_SERIAL_NUMBER_ARN (optional)'

            if args.command == 'mfa':
                if not mfa_required:
                    logger.log("MFA is not configured in config.env. Skip authentication.")
                    return
                mfa_token = getpass.getpass("Enter MFA Token: ")
                credentials = s3_handler.get_mfa_session_token(config, mfa_token)
                s3_handler.save_session(credentials, session_file)
                logger.log("MFA authentication successful. Session saved.")
                return

            if mfa_required:
                session_data = s3_handler.load_session(session_file)
                if not s3_handler.is_session_valid(session_data):
                    raise ValueError("MFAセッションが期限切れか、実行されていません。'mfa'コマンドを先に実行してください。")

            # 3. Get S3 Client
            logger.log("Connecting to Wasabi...")
            s3_client = s3_handler.get_s3_client(config, session_data=session_data)
            logger.log("Connection successful.")

            bucket_name = config['bucket_name']
            logger.log_debug(f"Using bucket: {bucket_name}")

            # 4. Execute Command
            if args.command == 'download_file':
                destination_path = args.destination if args.destination else os.path.join(get_default_download_dir(), os.path.basename(args.source))
                logger.log(f"Analyzing file '{args.source}'...")
                file_info = s3_handler.get_object_info(s3_client, bucket_name, args.source)
                total_size = file_info['Size']

                logger.log(f"Found 1 file with total size of {format_bytes(total_size)}.")
                logger.log(f"Downloading to '{destination_path}'...")

                with tqdm(total=total_size, unit='B', unit_scale=True, desc=os.path.basename(args.source)) as pbar:
                    s3_handler.download_file(
                        s3_client, bucket_name, args.source, destination_path, pbar.update
                    )
                logger.log(f"\nSuccessfully downloaded 1 file.")

            elif args.command == 'list_files':
                logger.log(f"Listing files in: '{args.source if args.source else 'bucket root'}'")
                object_list, _ = s3_handler.list_objects_in_prefix(s3_client, bucket_name, args.source)

                if not object_list:
                    logger.log("No files found in the specified path.")
                    return

                for obj in object_list:
                    logger.log(obj['Key'])

                logger.log(f"\nTotal files found: {len(object_list)}")

            elif args.command in ['download_dir', 'download_versioned']:
                destination_dir = args.destination if args.destination else get_default_download_dir()

                object_list = []
                total_size = 0

                logger.log(f"Analyzing files in '{args.source if args.source else 'bucket root'}'...")
                if args.command == 'download_dir':
                    object_list, total_size = s3_handler.list_objects_in_prefix(s3_client, bucket_name, args.source)
                else: # download_versioned
                    try:
                        ts = datetime.datetime.strptime(args.timestamp, '%Y%m%d').replace(hour=23, minute=59, second=59, microsecond=999999)
                        ts = ts.replace(tzinfo=datetime.timezone.utc)
                        logger.log_debug(f"Recovery timestamp: {ts}")
                    except ValueError:
                        raise ValueError("Invalid timestamp format. Please use YYYYMMDD.")
                    object_list, total_size = s3_handler.list_object_versions_at_timestamp(s3_client, bucket_name, ts, args.source)

                file_count = len(object_list)
                if file_count == 0:
                    logger.log("No files found to download.")
                    return

                logger.log(f"Found {file_count} files to download with a total size of {format_bytes(total_size)}.")
                logger.log(f"Downloading to '{destination_dir}'...")

                with tqdm(total=total_size, unit='B', unit_scale=True, desc="Total Progress") as pbar:
                    s3_handler.download_objects(
                        s3_client, bucket_name, destination_dir, args.source, object_list, pbar.update
                    )

                logger.log(f"\nSuccessfully downloaded {file_count} files.")

        except (FileNotFoundError, ValueError, ClientError) as e:
            logger.log_error(str(e))
            sys.exit(1)
        except Exception as e:
            logger.log_error(f"An unexpected error occurred: {e}")
            sys.exit(1)
    
    finally:
        # Always close the logger
        logger.close_logger()


if __name__ == '__main__':
    main()
