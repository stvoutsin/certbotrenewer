import paramiko
import subprocess
import os
from datetime import datetime
import argparse

__all__ = ["CertificateRenewer", "SSHConnection"]

import logging


class CustomLogger:
    def __init__(self, log_dir, log_file):
        # Create a logger
        self.logger = logging.getLogger("custom_logger")
        self.logger.setLevel(logging.DEBUG)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        log_file = os.path.join(log_dir, log_file)

        # Create a file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(
            logging.DEBUG
        )  # You can adjust the log level for the file handler as needed
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # Create a console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(
            logging.DEBUG
        )  # You can adjust the log level for the console handler as needed
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def debug(self, message):
        self.logger.debug(message)

    def error(self, message):
        self.logger.error(message)

    def warning(self, message):
        self.logger.warning(message)

    def info(self, message):
        self.logger.info(message)


class SSHConnection:
    """
    SSH Context manager
    """

    def __init__(self, host, user):
        self.host = host
        self.user = user
        self.ssh_connection = None

    def __enter__(self):
        self.ssh_connection = self._ssh_connect()
        return self.ssh_connection

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ssh_connection:
            self.ssh_connection.close()

    def _ssh_connect(self):
        ssh_connection = paramiko.SSHClient()
        ssh_connection.load_system_host_keys()
        ssh_connection.connect(self.host, username=self.user)
        return ssh_connection


class CertificateRenewer:
    """
    Handles renewing a certificate via ssh connection and certbot
    """

    def __init__(
        self,
        ssh_connection,
        remote_user,
        remote_host,
        backup_destination,
        remote_folder,
        tar_name,
        logger = logging.getLogger(__name__),
    ):
        self.ssh = ssh_connection
        self.remote_host = remote_host
        self.remote_user = remote_user
        self.backup_destination = backup_destination
        self.remote_folder = remote_folder
        self.tar_name = tar_name
        self.current_date = datetime.now().strftime("%Y%m%d")
        self.logger = logger

    @property
    def tarball_path(self):
        return f"{self.remote_folder}/{self.tar_name}"

    def renew_ssl_certificate(self):
        """
        Renew SSL certificate on the remote server using certbot.

        Returns:
            bool: True if certificate renewal was successful, False otherwise.
        """
        stdout = ""
        try:
            _, stdout, _ = self.ssh.exec_command("sudo certbot renew --quiet")
            return b"No renewals were attempted" not in stdout
        except Exception:
            self.logger.error(f"Error during certificate renewal: {stdout}")
            return False

    def create_certificate_tarball(self):
        """
        Create a tarball of SSL certificates on the remote server.

        Returns:
            str: The path to the created tarball, or None on failure.
        """
        try:
            self.ssh.exec_command(
                f"sudo tar -cvzf {self.tarball_path} -C /etc/ letsencrypt"
            )
            return self.tarball_path
        except Exception as e:
            self.logger.error(f"Error during certificate tarball creation: {e}")
            return None

    def copy_certificate_to_data_node(self):
        """
        Copy the certificate tarball from the remote server to the data node using SCP.

        Returns:
            bool: True if the copy operation was successful, False otherwise.
        """
        try:
            target_directory = os.path.join(self.backup_destination, self.current_date)
            os.makedirs(target_directory, exist_ok=True)
            target_path = os.path.join(
                target_directory, os.path.basename(self.tarball_path)
            )
            subprocess.run(
                [
                    "scp",
                    f"{self.remote_user}@{self.remote_host}:{self.tarball_path}",
                    target_path,
                ]
            )

            return True

        except Exception as e:
            self.logger.error(f"Error during copying: {e}")
            return False

    def update_latest_symlink(self):
        """
        Update the "latest" symlink to point to the new directory.
        """
        try:
            latest_symlink = os.path.join(self.backup_destination, "latest")
            if os.path.islink(latest_symlink):
                os.remove(latest_symlink)
            os.symlink(self.current_date, latest_symlink)
            self.logger.info(f"Updated 'latest' symlink to {self.current_date}")
        except Exception as e:
            self.logger.error(f"Error updating 'latest' symlink: {e}")

    def renew_and_copy_certificate(self):
        """
        Renew and Copy certificate from remote server
        """
        self.logger.info("Starting Renewal & Backup")
        if self.renew_ssl_certificate():
            tarball_path = self.create_certificate_tarball()
            if tarball_path:
                if self.copy_certificate_to_data_node():
                    self.update_latest_symlink()
                    self.logger.info("Renewal completed successfully")


def main(args):
    # Define the log directory and log filename
    log_directory = "logs"
    log_filename = "app.log"

    # Initialize the custom logger with the log directory and log filename
    custom_logger = CustomLogger(log_directory, log_filename)

    zeppelin_host = args.zeppelin_host
    zeppelin_user = args.zeppelin_user
    data_backup_dest = args.data_backup_dest

    # Define certs name
    zeppelin_tmp_folder = "/tmp"
    cert_tarname = "certs.tar.gz"

    # Define the local destination path on the data node

    with SSHConnection(zeppelin_host, zeppelin_user) as ssh:
        renewer = CertificateRenewer(
            ssh_connection=ssh,
            remote_user=zeppelin_user,
            remote_host=zeppelin_host,
            backup_destination=data_backup_dest,
            remote_folder=zeppelin_tmp_folder,
            tar_name=cert_tarname,
            logger=custom_logger,
        )
        renewer.renew_and_copy_certificate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Renew and copy SSL certificates on a remote server."
    )
    parser.add_argument(
        "--zeppelin-host",
        required=True,
        help="Hostname or IP address of the remote server.",
    )
    parser.add_argument(
        "--zeppelin-user",
        required=True,
        help="Username for SSH connection to the remote server.",
    )
    parser.add_argument(
        "--data-backup-dest",
        required=True,
        help="Destination path on the data node.",
    )
    arguments = parser.parse_args()
    main(arguments)
