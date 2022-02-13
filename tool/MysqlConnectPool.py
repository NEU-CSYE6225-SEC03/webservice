import aiomysql

from tool.Config import Config
from tool.Logger import Logger


async def getCursor(pool):
    conn = await pool.acquire()
    cur = await conn.cursor()

    return conn, cur


class MysqlConnectPool(object):

    def __init__(self, loop, maxsize):
        self.connect_pool = None
        self.loop = loop
        self.maxsize = maxsize

        # read db config
        self.host = Config.getInstance()['MYSQL_IP']
        self.port = Config.getInstance()['MYSQL_PORT']
        self.user = Config.getInstance()['MYSQL_USERNAME']
        self.password = Config.getInstance()['MYSQL_PASSWORD']
        self.database = "webservice"

        self.loop.run_until_complete(self.createPool())

    async def createPool(self):
        self.connect_pool = await aiomysql.create_pool(loop=self.loop,
                                                       host=self.host, port=self.port,
                                                       user=self.user, password=self.password,
                                                       db=self.database, charset="utf8",
                                                       maxsize=self.maxsize, minsize=1)

    def getPool(self):
        return self.connect_pool

    async def waitClosePool(self):
        self.connect_pool.close()
        await self.connect_pool.wait_closed()

    def closePool(self):
        self.loop.run_until_complete(self.waitClosePool())

