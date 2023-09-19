# Certificate Renewal and Copy Script

Renew certificate via certbot and copy it to backup node

This Python script allows you to renew SSL certificates on a remote server and copy them to a local destination path on a data node. It uses SSH for remote operations and provides logging capabilities.

Prerequisites
Before using this script, ensure you have the following prerequisites installed:

Python 3.x
Required Python packages (Install them using `pip install -r requirements.txt`):

Usage
Clone this repository to your local machine:

bash
Copy code

    git clone <repository-url>

Navigate to the project directory:

bash
Copy code

    cd <project-directory>

Execute the script with the required command-line arguments. Use the following command format:

Copy code

    python certrenewer.py --zeppelin-host <hostname-or-ip> --zeppelin-user <username> --data-backup-dest <destination-path>

Arguments:

	  --zeppelin-host: The hostname or IP address of the remote server.
	  --zeppelin-user: Username for the SSH connection to the remote server.
	  --data-backup-dest: Destination path on the data node.
	  

The script will connect to the remote server, renew SSL certificates, and copy them to the specified local destination path on the data node.

Configuration
You can configure the log directory and log filename by modifying the log_directory and log_filename variables in the script.

The script assumes a default temporary folder (/tmp) and certificate tarball name (certs.tar.gz). Modify these variables (zeppelin_tmp_folder and cert_tarname) in the script as needed.

Customization
The script uses a custom logger module (<custom-logger-module>) for logging. Ensure that you have this module available and properly configured.

