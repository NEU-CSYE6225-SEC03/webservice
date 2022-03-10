import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Add path of cwd to sys

import json
import asyncio
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
                            self.token_passed = True
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
                            self.token_passed = True


class HealthzHandler(BaseHandler):
    def get(self):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish()


class UserCreateHandler(BaseHandler):
    @tornado.gen.coroutine
    def post(self):
        try:
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
                self.finish()
                return

            # Validate duplicated username
            dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            usernameExist = yield dao.usernameExist(username)
            if usernameExist:
                Logger.getInstance().info('duplicated username[{username}]'.format(username=username))
                self.set_status(400)
                self.finish()
                return

            # create user
            password = encrypt(password)  # encrypt password
            isSuccess, respBodyDict = yield dao.createUser(first_name, last_name, username, password)
            if isSuccess:
                # respBodyDict['token'] = createToken(payload={"username": username, "password": password}, timeout=20)  # JWT token
                self.set_status(201)
                self.write(respBodyDict)
            else:
                self.set_status(500)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)
            self.set_status(501)
            self.finish()
            return


class UserInfoHandler(TokenHandler):
    @tornado.gen.coroutine
    def get(self):
        try:
            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(400)
                self.finish()
                return

            username = self.token_msg['username']
            dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            respBodyDict = yield dao.getUserInfoByUsername(username)
            respBodyDict.pop("password")
            self.set_status(200)
            self.write(respBodyDict)

        except Exception as e:
            Logger.getInstance().exception(e)

    @tornado.gen.coroutine
    def put(self):
        try:
            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(400)
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
                    self.finish()
                    return

            # Validate username exist
            dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            userInfo = yield dao.getUserInfoByUsername(username)
            if userInfo is None:
                Logger.getInstance().info('username[{username}] is not allowed to change'.format(username=username))
                self.set_status(400)
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
                self.finish()
            else:
                self.set_status(500)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)


class PictureHandler(TokenHandler):

    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Headers", "x-requested-with")
        self.set_header('Access-Control-Allow-Methods', 'POST, GET, DELETE')

    @tornado.gen.coroutine
    def post(self):
        try:
            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(400)
                self.finish()
                return

            # Grab uploaded file data
            files = self.request.files["profilePic"]
            if len(files) == 0:
                Logger.getInstance().info('Cannot receive any picture file')
                self.set_status(400)
                self.finish()

            file = files[0]
            file_name = file.get('filename', None)
            if file_name is None:
                Logger.getInstance().info('Cannot get picture file name')
                self.set_status(400)
                self.finish()

            file_data = file.get('body', None)
            if file_data is None:
                Logger.getInstance().info('Cannot get picture file data')
                self.set_status(400)
                self.finish()

            file_type = file.get('content_type', None)
            if file_type is None:
                Logger.getInstance().info('Cannot get picture file type')
                self.set_status(400)
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
                with open(file_data, 'rb') as f:
                    s3resource.Object(s3bucket_name, url).put(Body=f)

                yield img_dao.updateUserImage(file_name=file_name, url=url, user_id=user_id)
            else:
                """ S3 图片需要上传 """
                url = s3bucket_name + "/" + user_id + "/" + file_name
                with open(file_data, 'rb') as f:
                    s3resource.Object(s3bucket_name, url).put(Body=f)

                yield img_dao.createUserImage(file_name=file_name, url=url, user_id=user_id)

            # Make response
            resp_body = yield img_dao.getUserImage(user_id)

            self.set_status(201)
            self.write(resp_body)

        except Exception as err:
            Logger.getInstance().exception(err)
            self.set_status(400)
            self.finish()
            return

    @tornado.gen.coroutine
    def get(self):
        try:
            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(400)
                self.finish()
                return

            user_dao = UserDAO(connect_pool=MYSQL_CONN_POOL.getPool())
            sql_status, user_id = yield user_dao.getUserIdByUserName(username=self.token_msg['username'])
            img_dao = ImageDAO(connect_pool=MYSQL_CONN_POOL.getPool())

            img_exist = yield img_dao.userImageExist(user_id)
            if img_exist:
                resp_body = yield img_dao.getUserImage(user_id)

                self.set_status(200)
                self.write(resp_body)
            else:
                self.set_status(404)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)
            self.set_status(400)
            self.finish()
            return

    @tornado.gen.coroutine
    def delete(self):
        try:
            self.set_header("Content-Type", "application/json; charset=utf-8")  # set response header

            if not self.token_passed:
                Logger.getInstance().info('token auth fail')
                self.set_status(401)
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
                self.finish()
            else:
                self.set_status(404)
                self.finish()

        except Exception as err:
            Logger.getInstance().exception(err)


def make_app():
    return tornado.web.Application([
        (r"/healthz", HealthzHandler),
        (r"/v1/user", UserCreateHandler),
        (r"/v1/user/self", UserInfoHandler),
        (r"/v1/user/self/pic", PictureHandler),
    ])


if __name__ == "__main__":
    MYSQL_CONN_POOL = MysqlConnectPool(loop=asyncio.get_event_loop(), maxsize=10)
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
