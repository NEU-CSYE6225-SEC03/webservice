import uuid
import datetime

import pymysql

from tool.Config import Config
from tool.Logger import Logger


class UserDAO(object):

    def __init__(self, connect_pool):
        self.connect_pool = connect_pool

    async def usernameExist(self, username: str):
        selectResult = None
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute("SELECT id FROM user WHERE username = %s", [username, ])
                    selectResult = await cursor.fetchone()
                    Logger.getInstance().info('execute sql to determine exist of username[%s]' % username)

                except Exception as e:
                    Logger.getInstance().exception(e)

        return selectResult is not None

    async def getUserInfoByUsername(self, username: str):
        selectResult = None
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        "SELECT id, first_name, last_name, username, password, account_created, account_updated FROM user WHERE userName = %s",
                        [username, ])
                    Logger.getInstance().info('execute sql to get info of user by username[%s]' % username)
                    selectResult = await cursor.fetchone()

                except Exception as e:
                    Logger.getInstance().exception(e)

        if selectResult is not None:
            return {
                'id': selectResult[0],
                'first_name': selectResult[1],
                'last_name': selectResult[2],
                'username': selectResult[3],
                'password': selectResult[4],
                'account_created': selectResult[5].strftime("%Y-%m-%d %H:%M:%S"),
                'account_updated': selectResult[6].strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return None

    async def updateUser(self, first_name: str, last_name: str, username: str, password: str):
        affectRowNum = 0
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    affectRowNum = await cursor.execute(
                        "UPDATE user SET first_name = %s, last_name = %s, password = %s, account_updated = %s where username = %s",
                        [first_name,
                         last_name,
                         password,
                         datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         username, ])

                    Logger.getInstance().info('execute sql to update info of user by username[%s]' % username)
                    await conn.commit()
                except Exception as e:
                    Logger.getInstance().exception(e)

        if affectRowNum:
            return True
        else:
            return False

    async def createUser(self, first_name: str, last_name: str, username: str, password: str):
        table = 'user'
        data = {
            'id': str(uuid.uuid1()),
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'password': password,
            'account_created': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'account_updated': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        keys = ', '.join(data.keys())
        values = ', '.join(['%s'] * len(data))
        insert_sql = "INSERT INTO {table} ({keys}) VALUES ({values})".format(table=table, keys=keys, values=values)

        affectRowNum = 0
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    affectRowNum = await cursor.execute(insert_sql, tuple(data.values()))
                    await conn.commit()
                    Logger.getInstance().info(
                        'execute sql of inserting a user, affectRowNum[{}], insert sql[{}], values[{}]'.format(
                            affectRowNum, insert_sql, tuple(data.values())))

                except Exception as e:
                    Logger.getInstance().exception(e)

        data.pop("password")
        if affectRowNum:
            return True, data
        else:
            return False, data
