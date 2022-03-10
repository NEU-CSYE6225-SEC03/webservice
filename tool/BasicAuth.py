import base64


def isBasicAuth(token: str) -> bool:
    return token.startswith("Basic ")


def parseBasicAuth(token: str) -> dict:
    result = {'status': False, 'data': None, 'error': None}
    try:
        token = token.lstrip("Basic ")
        token = str(base64.b64decode(token), "utf-8")
        if token.count(":") != 1:  # 格式为 username:password
            result['error'] = 'token 格式错误'
            return result

        username, password = token.split(':')
        result['data'] = {
            'username': username,
            'password': password
        }

        result['status'] = True
    except Exception as err:
        result['error'] = 'token 未知错误，可能是格式错误'

    return result


if __name__ == '__main__':
    token = "Basic aGNqQGdtYWlsLmNvbToxMjM0NTY="
    print(isBasicAuth(token))
    result = parseBasicAuth(token)
    print(result)

    if result["status"]:
        data = result["data"]
        if data is not None:
            token_msg = result["data"]
            username = token_msg.get("username", None)
            print(username)
            password = token_msg.get("password", None)
            print(password)
