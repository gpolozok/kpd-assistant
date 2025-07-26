import argparse
import sys

from kpd_assistant.bot.bot import Bot
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

    bot = Bot()
    bot.run()