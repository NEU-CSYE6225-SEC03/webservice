import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Add path of cwd to sys
import json
import asyncio
from io import BytesIO
import time

import statsd
import tornado.web
import tornado.ioloop
import tornado.httpserver
import tornado.gen
import boto3

from tool.Config import Config
from tool.Logger import Logger
from tool.regexTool import isValidEmail
from tool.cryptTool import encrypt, checkSame
from tool.BasicAuth import isBasicAuth, parseBasicAuth
from tool.JwtAuth import createToken, parsePayload
from tool.MysqlConnectPool import MysqlConnectPool
from dao.UserDAO import UserDAO
from dao.ImageDAO import ImageDAO


class BaseHandler(tornado.web.RequestHandler):
    @tornado.gen.coroutine
    def prepare(self):
        super(BaseHandler, self).prepare()

    def set_default_headers(self):
        super().set_default_headers()


class TokenHandler(BaseHandler):
    @tornado.gen.coroutine
    def prepare(self):
        # 通过 Authorization 请求头传递 token
        head = self.request.headers
        token = head.get("Authorization", "")
        self.token_passed = False

        if isBasicAuth(token):
            # basic auth token
            result = parseBasicAuth(token)
            if result["status"]:
                data = result["data"]
                if data is not None:
                    self.token_msg = result["data"]  # dict in json format
                    username = self.token_msg.get("username", None)
                    password = self.token_msg.get("password", None)
                    if username is not None and password is not None:
                        dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
                        userInfo = yield dao.getUserInfoByUsername(username)
                        if userInfo is not None and (username == userInfo["username"] and checkSame(password, userInfo["password"])):
                            username_verified = yield dao.usernameVerified(username)
                            if username_verified:
                                Logger.getInstance().info('Username from basic token is verified!')
                                self.token_passed = True
                            else:
                                Logger.getInstance().info('Username from basic token is unverified......')
                        else:
                            Logger.getInstance().info('Username and password from basic token are unmatched with database')
        else:
            # jwt auth token
            result = parsePayload(token)
            if result["status"]:
                # 解析 payload, 提取 username 和 password 进行比对
                data = result["data"]
                if data is not None:
                    # self.token_msg = json.dumps(result, ensure_ascii=False)  # str in json format
                    self.token_msg = result["data"]  # dict in json format
                    username = self.token_msg.get("username", None)
                    password = self.token_msg.get("password", None)
                    if username is not None and password is not None:
                        dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
                        userInfo = yield dao.getUserInfoByUsername(username)
                        if userInfo is not None and (userInfo["username"] == username and userInfo["password"] == password):
                            username_verified = yield dao.usernameVerified(username)
                            if username_verified:
                                self.token_passed = True
                            else:
                                Logger.getInstance().info('Username from jwt token is unverified')
                        else:
                            Logger.getInstance().info('Username and password jwt from token are unmatched with database')


class HealthzHandler(BaseHandler):
    def get(self):
        service_start_time = time.time()
        STATSD_CONN.incr('[GET] healthz')
        self.set_header("Content-Type", "application/json; charset=utf-8")
        Logger.getInstance().info('hello old point')
        STATSD_CONN.timing('timing [GET] healthz ', (time.time() - service_start_time) * 1000)
        self.finish()


class HealthHandler(BaseHandler):
    def get(self):
        service_start_time = time.time()
        STATSD_CONN.incr('[GET] health')
        self.set_header("Content-Type", "application/json; charset=utf-8")
        Logger.getInstance().info('hello new point')
        STATSD_CONN.timing('timing [GET] health ', (time.time() - service_start_time) * 1000)
        self.finish()


class UserCreateHandler(BaseHandler):
    @tornado.gen.coroutine
    def post(self):
        service_start_time = time.time()
        try:
            STATSD_CONN.incr('[POST] /v1/user')

            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            data = json.loads(self.request.body)
            first_name = data.get('first_name', None)
            last_name = data.get('last_name', None)
            username = data.get('username', None)
            password = data.get('password', None)

            # Validate username
            if not isValidEmail(username):
                Logger.getInstance().info('{username} is not a valid email address'.format(username=username))
                self.set_status(400)
                STATSD_CONN.timing('timing [POST] /v1/user ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            # Validate duplicated username
            dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            usernameExist = yield dao.usernameExist(username)
            if usernameExist:
                Logger.getInstance().info('duplicated username[{username}]'.format(username=username))
                self.set_status(400)
                STATSD_CONN.timing('timing [POST] /v1/user ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            # create user
            password = encrypt(password)  # encrypt password
            isSuccess, respBodyDict = yield dao.createUser(first_name, last_name, username, password)
            if isSuccess:
                # 创建 token, ??? mins 后过期
                token = createToken(payload={}, timeout=999999999)

                # Publish sns, 触发 Lambda 操作, 操作 DynamoDb 并发邮件
                sns_client = boto3.client('sns', region_name='us-east-1')
                verify_link = "http://prod.weifenglai.me/v1/verifyUserEmail?email={username}&token={token}".format(username=username, token=token)
                sns_message = {
                    'email': username,
                    'token': token,
                    'verify_link': verify_link
                }
                Logger.getInstance().info('sns_message: {msg}'.format(msg=sns_message))
                Logger.getInstance().info('TopicArn: {TopicArn}'.format(TopicArn=Config.getInstance()['SNSTopic']))
                sns_client.publish(TopicArn=Config.getInstance()['SNSTopic'],
                                   Message=json.dumps(sns_message))

                # respBodyDict['token'] = createToken(payload={"username": username, "password": password}, timeout=20)  # JWT token
                self.set_status(201)
                STATSD_CONN.timing('timing [POST] /v1/user ', (time.time() - service_start_time) * 1000)
                # self.write(respBodyDict)

                respBodyDict['TopicArn'] = Config.getInstance()['SNSTopic']
                respBodyDict['sns_message'] = str(sns_message)
                self.write(respBodyDict)
            else:
                self.set_status(500)
                STATSD_CONN.timing('timing [POST] /v1/user ', (time.time() - service_start_time) * 1000)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)
            self.set_status(501)
            STATSD_CONN.timing('timing [POST] /v1/user ', (time.time() - service_start_time) * 1000)
            self.finish()
            return


class UserVerifyHandler(BaseHandler):
    @tornado.gen.coroutine
    def get(self):
        service_start_time = time.time()
        try:
            STATSD_CONN.incr('[GET] /v1/verifyUserEmail')

            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header
            username = self.get_argument('email', default=None)
            token = self.get_argument('token', default=None)

            if username is None or token is None:
                if username is None:
                    Logger.getInstance().info("can't get username from GET request API /v1/verifyUserEmail")
                if token is None:
                    Logger.getInstance().info("can't get token from GET request API /v1/verifyUserEmail")

                STATSD_CONN.timing('timing [GET] /v1/verifyUserEmail', (time.time() - service_start_time) * 1000)
                self.set_status(490)
                self.finish()
                return

            Logger.getInstance().info("get email & token from GET request API /v1/verifyUserEmail, email is {email}, token is {token}".format(email=username, token=token))

            # 根据 ttl 查 DynamoDB, 查看 record 有没有过期
            db_resource = boto3.resource('dynamodb')
            table = db_resource.Table('verification')
            search_response = table.get_item(
                Key={
                    "email": username
                }
            )
            if 'Item' in search_response:
                Logger.getInstance().info('find record in dynamodb with email {}'.format(username))
            else:
                Logger.getInstance().info('Cannot find record in dynamodb with email {}, probably record is expired'.format(username))
                self.set_status(491)
                STATSD_CONN.timing('timing [GET] /v1/verifyUserEmail', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            # 判断 get 带的 token 是否过期, 以及 one-time use
            token_good = parsePayload(token).get("status")
            if not token_good:
                Logger.getInstance().info('Token error, probably it has been expired, token info[{}]'.format(token))
                self.set_status(492)
                STATSD_CONN.timing('timing [GET] /v1/verifyUserEmail', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            if token in TOKEN_SET:
                Logger.getInstance().info('One-time token was used, token info[{}]'.format(token))
                self.set_status(493)
                STATSD_CONN.timing('timing [GET] /v1/verifyUserEmail', (time.time() - service_start_time) * 1000)
                self.finish()
                return
            else:
                TOKEN_SET.add(token)

            dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            is_success = yield dao.updateVerifiedByUsername(username)

            respBodyDict = yield dao.getUserInfoByUsername(username)
            self.set_status(666)
            self.write(respBodyDict)

            if is_success:
                Logger.getInstance().info('update user verification successfully, username[%s]' % username)
                self.set_status(200)
                STATSD_CONN.timing('timing [GET] /v1/verifyUserEmail', (time.time() - service_start_time) * 1000)
                self.finish()
            else:
                Logger.getInstance().info('Failed to update user verification, username[%s]' % username)
                self.set_status(494)
                STATSD_CONN.timing('timing [GET] /v1/verifyUserEmail', (time.time() - service_start_time) * 1000)
                self.finish()

        except Exception as e:

            self.set_status(999)
            self.write(str(e))

            Logger.getInstance().exception(e)
            STATSD_CONN.timing('timing [GET] /v1/verifyUserEmail', (time.time() - service_start_time) * 1000)
            return


class UserInfoHandler(TokenHandler):
    @tornado.gen.coroutine
    def get(self):
        service_start_time = time.time()
        try:
            STATSD_CONN.incr('[GET] /v1/user/self')

            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(470)
                STATSD_CONN.timing('timing [GET] /v1/user/self ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            username = self.token_msg['username']
            dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            respBodyDict = yield dao.getUserInfoByUsername(username)
            respBodyDict.pop("password")
            self.set_status(200)
            STATSD_CONN.timing('timing [GET] /v1/user/self ', (time.time() - service_start_time) * 1000)
            self.write(respBodyDict)

        except Exception as e:
            Logger.getInstance().exception(e)
            STATSD_CONN.timing('timing [GET] /v1/user/self ', (time.time() - service_start_time) * 1000)
            return

    @tornado.gen.coroutine
    def put(self):
        service_start_time = time.time()
        try:
            STATSD_CONN.incr('[PUT] /v1/user/self')

            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(400)
                STATSD_CONN.timing('timing [PUT] /v1/user/self ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            data = json.loads(self.request.body)
            first_name = data.get('first_name', None)
            last_name = data.get('last_name', None)
            username = data.get('username', None)
            password = data.get('password', None)

            # check fields
            allowFields = set()
            allowFields.add('first_name')
            allowFields.add('last_name')
            allowFields.add('username')
            allowFields.add('password')
            for key in data.keys():
                if key not in allowFields:
                    Logger.getInstance().info('Only allow modify first_name, last_name, and password')
                    self.set_status(400)
                    STATSD_CONN.timing('timing [PUT] /v1/user/self ', (time.time() - service_start_time) * 1000)
                    self.finish()
                    return

            # Validate username exist
            dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            userInfo = yield dao.getUserInfoByUsername(username)
            if userInfo is None:
                Logger.getInstance().info('username[{username}] is not allowed to change'.format(username=username))
                self.set_status(400)
                STATSD_CONN.timing('timing [PUT] /v1/user/self ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            # update user
            # 由于 update sql 只有固定一条, 所以这四个字段都不能为空
            if first_name is None:
                first_name = userInfo['first_name']

            if last_name is None:
                last_name = userInfo['last_name']

            if password is None:
                password = userInfo['password']
            else:
                password = encrypt(password)  # encrypt password

            isSuccess = yield dao.updateUser(first_name, last_name, username, password)
            if isSuccess:
                Logger.getInstance().info('update user successfully, username[%s]' % username)
                self.set_status(204)
                STATSD_CONN.timing('timing [PUT] /v1/user/self ', (time.time() - service_start_time) * 1000)
                self.finish()
            else:
                self.set_status(500)
                STATSD_CONN.timing('timing [PUT] /v1/user/self ', (time.time() - service_start_time) * 1000)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)
            STATSD_CONN.timing('timing [PUT] /v1/user/self ', (time.time() - service_start_time) * 1000)


class PictureHandler(TokenHandler):

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, DELETE')

    @tornado.gen.coroutine
    def post(self):
        service_start_time = time.time()
        try:
            STATSD_CONN.incr('[POST] /v1/user/self/pic')

            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(400)
                STATSD_CONN.timing('timing [POST] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            # Grab uploaded file data
            files = self.request.files["profilePic"]
            if len(files) == 0:
                Logger.getInstance().info('Cannot receive any picture file')
                self.set_status(400)
                STATSD_CONN.timing('timing [POST] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()

            file = files[0]
            file_name = file.get('filename', None)
            if file_name is None:
                Logger.getInstance().info('Cannot get picture file name')
                self.set_status(400)
                STATSD_CONN.timing('timing [POST] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()

            file_data = file.get('body', None)
            if file_data is None:
                Logger.getInstance().info('Cannot get picture file data')
                self.set_status(400)
                STATSD_CONN.timing('timing [POST] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()

            file_type = file.get('content_type', None)
            if file_type is None:
                Logger.getInstance().info('Cannot get picture file type')
                self.set_status(400)
                STATSD_CONN.timing('timing [POST] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()

            # Get user info
            user_dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            sql_status, user_id = yield user_dao.getUserIdByUserName(username=self.token_msg['username'])

            # Add or update image info
            img_dao = ImageDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            img_exist = yield img_dao.userImageExist(user_id)

            s3resource = boto3.resource('s3')
            s3bucket_name = Config.getInstance()['S3BUCKETNAME']

            if img_exist:
                image_record = yield img_dao.getUserImage(user_id)
                url = image_record['url']
                """ S3 删除旧图片 """
                s3resource.Object(s3bucket_name, url).delete()

                """ S3 上传新图片 """
                url = s3bucket_name + "/" + user_id + "/" + file_name
                s3resource.Object(s3bucket_name, url).put(Body=BytesIO(file_data))

                yield img_dao.updateUserImage(file_name=file_name, url=url, user_id=user_id)
            else:
                """ S3 图片需要上传 """
                url = s3bucket_name + "/" + user_id + "/" + file_name
                s3resource.Object(s3bucket_name, url).put(Body=BytesIO(file_data))

                yield img_dao.createUserImage(file_name=file_name, url=url, user_id=user_id)

            # Make response
            resp_body = yield img_dao.getUserImage(user_id)

            self.set_status(201)
            STATSD_CONN.timing('timing [POST] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
            self.write(resp_body)

        except Exception as err:
            Logger.getInstance().exception(err)
            self.set_status(400)
            STATSD_CONN.timing('timing [POST] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
            self.finish()
            return

    @tornado.gen.coroutine
    def get(self):
        service_start_time = time.time()
        try:
            STATSD_CONN.incr('[GET] /v1/user/self/pic')

            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(400)
                STATSD_CONN.timing('timing [GET] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            user_dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            sql_status, user_id = yield user_dao.getUserIdByUserName(username=self.token_msg['username'])
            img_dao = ImageDAO(connect_pool=MYSQL_CONN_POOL.getPool())

            img_exist = yield img_dao.userImageExist(user_id)
            if img_exist:
                resp_body = yield img_dao.getUserImage(user_id)

                self.set_status(200)
                STATSD_CONN.timing('timing [GET] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.write(resp_body)
            else:
                self.set_status(404)
                STATSD_CONN.timing('timing [GET] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)
            self.set_status(400)
            STATSD_CONN.timing('timing [GET] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
            self.finish()
            return

    @tornado.gen.coroutine
    def delete(self):
        service_start_time = time.time()
        try:
            STATSD_CONN.incr('[DELETE] /v1/user/self/pic')

            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(401)
                STATSD_CONN.timing('timing [DELETE] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()
                return

            user_dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            sql_status, user_id = yield user_dao.getUserIdByUserName(username=self.token_msg['username'])
            img_dao = ImageDAO(connect_pool=MYSQL_CONN_POOL.getPool())

            img_exist = yield img_dao.userImageExist(user_id)
            if img_exist:
                """ S3 操作 删除图片 """
                s3resource = boto3.resource('s3')
                s3bucket_name = Config.getInstance()['S3BUCKETNAME']
                image_record = yield img_dao.getUserImage(user_id)
                url = image_record['url']
                s3resource.Object(s3bucket_name, url).delete()

                # 删除 DB metadata
                yield img_dao.deleteUserImage(user_id)

                self.set_status(204)
                STATSD_CONN.timing('timing [DELETE] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()
            else:
                self.set_status(404)
                STATSD_CONN.timing('timing [DELETE] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)
            STATSD_CONN.timing('timing [DELETE] /v1/user/self/pic ', (time.time() - service_start_time) * 1000)


def make_app():
    return tornado.web.Application([
        (r"/healthz", HealthzHandler),
        (r"/health", HealthHandler),
        (r"/v1/user", UserCreateHandler),
        (r"/v1/verifyUserEmail", UserVerifyHandler),
        (r"/v1/user/self", UserInfoHandler),
        (r"/v1/user/self/pic", PictureHandler),
    ])


if __name__ == "__main__":
    MYSQL_CONN_POOL = MysqlConnectPool(loop=asyncio.get_event_loop(), maxsize=10)
    STATSD_CONN = statsd.StatsClient('localhost', 8125)  # statsd
    TOKEN_SET = set()
    try:
        Logger.getInstance().info('=====service start======')
        app = make_app()
        server = tornado.httpserver.HTTPServer(app)
        server.listen(Config.getInstance()['PORT'], Config.getInstance()['IP'])
        server.start(1)
        tornado.ioloop.IOLoop.current().start()
    except KeyboardInterrupt:
        Logger.getInstance().info('=====service end======')
        Logger.getInstance().exception(KeyboardInterrupt)
    except Exception as e:
        Logger.getInstance().exception(e)
    finally:
        MYSQL_CONN_POOL.closePool()
        tornado.ioloop.IOLoop.current().stop()
