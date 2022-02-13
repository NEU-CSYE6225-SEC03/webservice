import jwt
import datetime
from jwt import exceptions

JWT_SALT = 'huoyingwhw666'


def create_token(payload, timeout=20) -> str:
    """
    :param payload:  例如：{'user_id':1,'username':'whw'}用户信息
    :param timeout: token的过期时间，默认20分钟
    :return:
    """
    headers = {
        'typ': 'jwt',
        'alg': 'HS256'
    }
    payload['exp'] = datetime.datetime.utcnow() + datetime.timedelta(minutes=timeout)
    result = jwt.encode(payload=payload, key=JWT_SALT, algorithm="HS256", headers=headers)

    return result


def parse_payload(token) -> dict:
    """
    对token进行和发行校验并获取payload
    :param token:
    :return:
    """
    result = {'status': False, 'data': None, 'error': None}
    try:
        verified_payload = jwt.decode(token, JWT_SALT, ['HS256'])
        result['status'] = True
        result['data'] = verified_payload
    except exceptions.ExpiredSignatureError:
        result['error'] = 'token已失效'
    except jwt.DecodeError:
        result['error'] = 'token认证失败'
    except jwt.InvalidTokenError:
        result['error'] = '非法的token'

    return result


if __name__ == '__main__':
    token = "eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VybmFtZSI6IjY2NzE2QGdtYWlsLmNvbSIsImV4cCI6MTY0NDcwMDUwOX0.imv6vv9S6Vzq2ywOVBOAUeiNxfeD3VTdU1HaaUcoA3s"
    res = parse_payload(token)
    print(res)
