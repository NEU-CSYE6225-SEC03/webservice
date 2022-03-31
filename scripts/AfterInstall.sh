sudo kill -9 `ps -ef |grep python3 |grep service_main.py | awk '{print $2}'`
sudo cp /home/ec2-user/service_main.py /home/ec2-user/webservice/service/
