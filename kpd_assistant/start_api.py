import argparse
import sys
import uvicorn

from kpd_assistant.api.api import app
from kpd_assistant.lib.config import Config


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--config',
        type=str,
        default='kpd_assistant/conf'
    )
    options = parser.parse_args(sys.argv[1:])

    Config.setup(config_dir=options.config)

    uvicorn.run(app, host="0.0.0.0", port=8001)
