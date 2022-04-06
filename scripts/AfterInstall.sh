sudo systemctl stop webservice.service

sudo cp /home/ec2-user/service_main.py /home/ec2-user/webservice/service/

sudo cp /home/ec2-user/cloudwatch-config.json /home/ec2-user/webservice/

sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/home/ec2-user/webservice/cloudwatch-config.json -s

sudo systemctl start amazon-cloudwatch-agent.service
