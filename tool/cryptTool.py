import bcrypt
import base64


def encodeBase64(b: bytes) -> str:
    return base64.b64encode(b)


def decodeBase64(s: str) -> bytes:
    return base64.b64decode(s)


def encrypt(s: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(s.encode(), salt)

    return encodeBase64(hashed)


def checkSame(s: str, hashed: str) -> bool:
    return bcrypt.checkpw(s.encode(), decodeBase64(hashed))


if __name__ == '__main__':
    passwd = '123456'
    code = encrypt(passwd)
    print(checkSame('123456', code))
    print(checkSame('123456', code))
