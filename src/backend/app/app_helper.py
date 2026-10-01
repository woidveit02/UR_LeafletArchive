import logging
import logging.config
import json
import pathlib

logger = logging.getLogger(__name__)

# https://www.youtube.com/watch?v=9L77QExPmI0
def setup_logging():
    config_file = pathlib.Path(__file__).resolve().parent / 'logs' / 'config.json'

    with open(config_file, encoding='utf-8') as f:
        config = json.load(f)

    file_handler = config.get('handlers', {}).get('file')
    if file_handler and file_handler.get('filename'):
        log_path = pathlib.Path(file_handler['filename'])

        if not log_path.parent.exists():
            log_path = config_file.parent / log_path.name
            file_handler['filename'] = str(log_path)

        log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.config.dictConfig(config)