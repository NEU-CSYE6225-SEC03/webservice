sudo kill -9 `ps -ef |grep python3 |grep service_main.py | awk '{print $2}'`
