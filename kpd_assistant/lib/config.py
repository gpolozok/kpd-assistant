import json
import os.path
import logging
import re

from kpd_assistant.lib.vault_client import VaultClient

default_config_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "conf"
)

log = logging.getLogger("system")


class Config:
    project = None

    @classmethod
    def setup(cls, config_dir=default_config_dir):
        main_config_file = os.path.join(config_dir, "project.json")
        with open(main_config_file) as fp:
            cls.project = json.load(fp)
        cls.vault_substitution()
        log.info("Setuped telegram bot config")

    @classmethod
    def vault_substitution(cls):
        if not cls.project.get('vault'):
            log.debug('Vault config is not set. Skipping substitution')
            return
        connect_string = cls.project['vault'].get('connect_string')
        if not connect_string:
            log.debug('Vault connect_string is not set. Skipping substitution')
            return
        mount_point = cls.project['vault'].get('mount_point')
        if not mount_point:
            log.debug('Vault mount_point is not set. Skipping substitution')
            return
        user = cls.project['vault'].get('user')
        if not user:
            log.debug('Vault user is not set. Skipping substitution')
            return
        password_file = cls.project['vault'].get('password_file')
        if not password_file:
            log.debug('Vault password_file is not set. Skipping substitution')
            return

        vault = VaultClient()
        vault.setup(connect_string, mount_point, user, password_file)

        # Only searching in dicts is supported.
        current_nodes = [cls.project]
        while current_nodes:
            next_nodes = []
            for node in current_nodes:
                for key, value in node.items():
                    if isinstance(value, dict):
                        next_nodes.append(value)
                    elif isinstance(value, str):
                        m = re.search(r'^VAULT:(\S+):(\S+)$', value)
                        if m:
                            node[key] = vault.get_value(m.group(1), m.group(2))
            current_nodes = next_nodes
