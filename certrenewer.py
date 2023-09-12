import logging
import paramiko
import subprocess
import os
from datetime import datetime


class SSHConnection:
    """
    SSH Context manager
    """

    def __init__(self, remote_host, remote_user):
        self.remote_host = remote_host
        self.remote_user = remote_user
        self.ssh = None

    def __enter__(self):
        self.ssh = self._ssh_connect()
        return self.ssh

    def __exit__(self, exc_type, exc_value, traceback):
        if self.ssh:
            self.ssh.close()

    def _ssh_connect(self):
        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.connect(self.remote_host, username=self.remote_user)
        return ssh


class CertificateRenewer:
    """
    Handles renewing a certificate via ssh connection and certbot
    """

    def __init__(self, ssh, remote_user, remote_host, local_destination):
        self.ssh = ssh
        self.remote_host = remote_host
        self.remote_user = remote_user
        self.local_destination = local_destination
        self.current_date = datetime.now().strftime("%Y%m%d")

    def renew_ssl_certificate(self):
        """
        Renew SSL certificate on the remote server using certbot.

        Returns:
            bool: True if certificate renewal was successful, False otherwise.
        """
        try:
            _, stdout, _ = self.ssh.exec_command("sudo certbot renew --quiet")
            return not b"No renewals were attempted" in stdout.read()
        except Exception as e:
            logging.error(f"Error during certificate renewal: {e}")
            return False

    def create_certificate_tarball(self):
        """
        Create a tarball of SSL certificates on the remote server.

        Returns:
            str: The path to the created tarball, or None on failure.
        """
        try:
            tarball_path = f"/tmp/certs.tar.gz"
            self.ssh.exec_command(f"tar czf {tarball_path} -C /etc/letsencrypt .")
            return tarball_path
        except Exception as e:
            logging.error(f"Error during certificate tarball creation: {e}")
            return None

    def copy_certificate_to_data_node(self):
        """
        Copy the certificate tarball from the remote server to the data node using SCP.

        Returns:
            bool: True if the copy operation was successful, False otherwise.
        """
        try:
            target_directory = os.path.join(self.local_destination, self.current_date)
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
            logging.error(f"Error during copying: {e}")
            return False

    def update_latest_symlink(self):
        """
        Update the "latest" symlink to point to the new directory.
        """
        try:
            latest_symlink = os.path.join(self.local_destination, "latest")
            if os.path.islink(latest_symlink):
                os.remove(latest_symlink)
            os.symlink(self.current_date, latest_symlink)
            print(f"Updated 'latest' symlink to {self.current_date}")
        except Exception as e:
            logging.error(f"Error updating 'latest' symlink: {e}")

    def close_ssh_connection(self):
        """
        Close the SSH connection.
        """
        self.ssh.close()

    def renew_and_copy_certificate(self):
        if self.renew_ssl_certificate():
            self.tarball_path = self.create_certificate_tarball()
            if self.tarball_path:
                if self.copy_certificate_to_data_node():
                    self.update_latest_symlink()


if __name__ == "__main__":
    # Define the remote server's details
    remote_host = "iris-gaia-blue.gaia-dmp.uk"
    remote_user = "fedora"

    # Define the local destination path on the data node
    local_destination = "/home/fedora/certs/"

    with SSHConnection(remote_host, remote_user) as ssh:
        renewer = CertificateRenewer(ssh, remote_user, remote_host, local_destination)
        renewer.renew_and_copy_certificate()

