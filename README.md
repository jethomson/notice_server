One Time
--------
cd notice_server
python3 -m venv venv
source ./venv/bin/activate
pip install -r requirements.txt
# need to run something like the following to get a self-signed SSL certificate if you want to use https: openssl req -new -x509 -days 999 -nodes -out ../server.pem -keyout ../server.pem

Every Time
----------
source ./venv/bin/activate
./notice_server.py # serves http on port 8080 by default. script uses #!./usr/bin/env python3 instead of the normal path to work around the issue of pip packages being required when running as root.


Example Usage
-------------
./notice_server.py             # runs http server on port 8080
./notice_server.py ssl         # runs https server of port 8080
sudo ./notice_server.py 80     # runs http server on port 80. It is not recommended to run this program with root permissions.
sudo ./notice_server.py 80 ssl # runs https server on port 80




