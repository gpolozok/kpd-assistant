import logging
import hvac

logger = logging.getLogger("system")


class VaultClient:
    def __init__(self):
        self.connection = None
        self.mount_point = None

    def setup(self, connect_string, mount_point, user, password_file):
        with open(password_file, 'r') as f:
            password = f.read().strip()
        self.connection = hvac.Client(url=connect_string)
        self.connection.auth_userpass(user, password)
        self.mount_point = mount_point

    def get_value(self, path, key):
        logger.debug('Vault: get value for %s %s', path, key)
        value = self.connection.secrets.kv.v1.read_secret(
            path, self.mount_point
        )['data'][key]
        return value
