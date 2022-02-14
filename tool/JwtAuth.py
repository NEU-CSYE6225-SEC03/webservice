import jwt
import datetime
from jwt import exceptions


def createToken(payload, timeout=20) -> str:
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
    key = "laiweifeng233"
    algorithm = "HS256"
    result = jwt.encode(payload=payload, key=key, algorithm=algorithm, headers=headers)

    return result


def parsePayload(token) -> dict:
    """
    对token进行和发行校验并获取payload
    :param token:
    :return:
    """
    result = {'status': False, 'data': None, 'error': None}
    key = "laiweifeng233"
    algorithms = ['HS256']
    try:
        verified_payload = jwt.decode(jwt=token, key=key, algorithms=algorithms)
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
    token = createToken(payload={'username': 'lwf@gg.com', 'password': '123'})
    res = parsePayload(token)
    print(res)
