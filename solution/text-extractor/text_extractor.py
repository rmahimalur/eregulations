import json
import logging
import re
from tempfile import TemporaryDirectory

import requests

from .backends import (
    BackendException,
    BackendInitException,
    FileBackend,
)
from .extractors import (
    Extractor,
    ExtractorException,
    ExtractorInitException,
)

logger = logging.getLogger(__name__)


def lambda_response(status_code: int, loglevel: int, message: str) -> dict:
    logging.log(loglevel, message)
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": message}),
    }


def lambda_success(message: str) -> dict:
    return lambda_response(200, logging.INFO, message)


def lambda_failure(status_code: int, message: str) -> dict:
    return lambda_response(status_code, logging.ERROR, message)


def handler(event: dict, context: dict) -> dict:
    # Retrieve configuration from event dict
    if "body" not in event:
        # Assume we are invoked directly
        config = event
    else:
        try:
            config = json.loads(event["body"])
        except Exception:
            return lambda_failure(400, "Unable to parse body as JSON.")

    # Retrieve required arguments
    try:
        resource_id = config["id"]
        uri = config["uri"]
        post_url = config["post_url"]
        token = config["token"]
    except KeyError:
        return lambda_failure(400, "You must include 'id', 'uri', 'token', and 'post_url' in the request body.")

    with TemporaryDirectory() as temp_dir:
        # Retrieve the file
        try:
            backend_type = config.get("backend", "web").lower()
            backend = FileBackend.get_backend(backend_type, config)
            file = backend.get_file(temp_dir, uri)
        except BackendInitException as e:
            return lambda_failure(500, f"Failed to initialize backend: {str(e)}")
        except BackendException as e:
            return lambda_failure(500, f"Failed to retrieve file: {str(e)}")
        except Exception as e:
            return lambda_failure(500, f"Backend unexpectedly failed: {str(e)}")

        try:
            file_type = uri.lower().split('.')[-1]
        except Exception as e:
            return lambda_failure(500, f"Failed to determine file type: {str(e)}")

        # Run extractor
        try:
            extractor = Extractor.get_extractor(file_type, config)
            text = extractor.extract(file)
        except ExtractorInitException as e:
            return lambda_failure(500, f"Failed to initialize text extractor: {str(e)}")
        except ExtractorException as e:
            return lambda_failure(500, f"Failed to extract text: {str(e)}")
        except Exception as e:
            return lambda_failure(500, f"Extractor unexpectedly failed: {str(e)}")

        # Strip unneeded data out of the extracted text
        text = re.sub(r'[\n\s]+', ' ', text).strip()

        # Send result to eRegs
        resp = ''
        header = {'Authorization': f'Bearer {token}'}
        try:
            resp = requests.post(
                post_url,
                headers=header,
                json={
                    "id": resource_id,
                    "text": text,
                },
                timeout=60,
            )
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            return lambda_failure(500, f"Failed to POST results: {str(e)}")
        except Exception as e:
            return lambda_failure(500, f"POST unexpectedly failed: {str(e)}")

        # Return success code
        return lambda_success(f"Function exited normally. {resp.content}")
