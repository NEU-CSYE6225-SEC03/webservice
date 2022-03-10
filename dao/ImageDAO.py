import uuid
import datetime

import pymysql

from tool.Config import Config
from tool.Logger import Logger


class ImageDAO(object):

    def __init__(self, connect_pool):
        self.connect_pool = connect_pool

    async def userImageExist(self, user_id: str):
        selectResult = None
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute("SELECT user_id FROM image WHERE user_id = %s", [user_id, ])
                    selectResult = await cursor.fetchone()
                    Logger.getInstance().info('execute sql to determine exist of image by user_id [%s]' % user_id)

                except Exception as e:
                    Logger.getInstance().exception(e)

        return selectResult is not None

    async def getUserImage(self, user_id: str):
        selectResult = None
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    await cursor.execute(
                        "SELECT id, file_name, user_id, url, upload_date FROM image WHERE user_id = %s",
                        [user_id, ])
                    Logger.getInstance().info('execute sql to get info of image by user_id[%s]' % user_id)
                    selectResult = await cursor.fetchone()

                except Exception as e:
                    Logger.getInstance().exception(e)

        if selectResult is not None:
            return {
                'id': selectResult[0],
                'file_name': selectResult[1],
                'user_id': selectResult[2],
                'url': selectResult[3],
                'upload_date': selectResult[4].strftime("%Y-%m-%d")
            }
        else:
            return None

    async def updateUserImage(self, file_name: str, url: str, user_id: str):
        affectRowNum = 0
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    affectRowNum = await cursor.execute(
                        "UPDATE image SET file_name = %s, url = %s, upload_date = %s where user_id = %s",
                        [file_name,
                         url,
                         datetime.datetime.now().strftime("%Y-%m-%d"),
                         user_id, ])

                    Logger.getInstance().info('execute sql for updating image info by user_id[%s]' % user_id)
                    await conn.commit()
                except Exception as e:
                    Logger.getInstance().exception(e)

        if affectRowNum:
            return True
        else:
            return False

    async def deleteUserImage(self, user_id: str):
        affectRowNum = 0
        async with self.connect_pool.acquire() as conn:
            async with conn.cursor() as cursor:
                try:
                    affectRowNum = await cursor.execute(
                        "DELETE FROM image WHERE user_id = %s",
                        [user_id, ]
                    )

                    Logger.getInstance().info('execute sql for deleting image info by user_id[%s]' % user_id)
                    await conn.commit()
                except Exception as e:
                    Logger.getInstance().exception(e)

        if affectRowNum:
            return True
        else:
            return False

    async def createUserImage(self, file_name: str, url: str, user_id: str):
        table = 'image'
        data = {
            'id': str(uuid.uuid1()),
            'file_name': file_name,
            'url': url,
            'user_id': user_id,
            'upload_date': datetime.datetime.now().strftime("%Y-%m-%d"),
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
                        'execute sql for inserting a image, affectRowNum[{}], insert sql[{}], values[{}]'.format(
                            affectRowNum, insert_sql, tuple(data.values())))

                except Exception as e:
                    Logger.getInstance().exception(e)

        if affectRowNum:
            return True, data
        else:
            return False, data
