import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # Add path of cwd to sys
import json
import asyncio
import tornado.web
import tornado.ioloop
import tornado.httpserver
import tornado.gen
from tool.Config import Config
from tool.Logger import Logger
from tool.regexTool import isValidEmail
from tool.cryptTool import encrypt, checkSame
from tool.JwtAuth import JWT_SALT, create_token, parse_payload
from tool.MysqlConnectPool import MysqlConnectPool
from dao.UserDAO import UserDAO


class BaseHandler(tornado.web.RequestHandler):
    def prepare(self):
        super(BaseHandler, self).prepare()

    def set_default_headers(self):
        super().set_default_headers()


class TokenHandler(BaseHandler):

    def prepare(self):
        # 通过 Authorization 请求头传递 token
        head = self.request.headers
        token = head.get("Authorization", "")
        result = parse_payload(token)
        if not result["status"]:
            self.token_passed = False
        else:
            self.token_passed = True

        # self.token_msg = json.dumps(result, ensure_ascii=False)  # str in json format
        self.token_msg = result  # dict in json format


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
                respBodyDict['token'] = create_token(payload={"username": username}, timeout=20)
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

            username = self.token_msg['data']['username']
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


def make_app():
    return tornado.web.Application([
        (r"/healthz", HealthzHandler),
        (r"/v1/user", UserCreateHandler),
        (r"/v1/user/self", UserInfoHandler),
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
