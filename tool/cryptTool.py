import bcrypt
import base64


def encodeBase64(b: bytes) -> str:
    return base64.b64encode(b).decode()


def decodeBase64(s: str) -> bytes:
    return base64.b64decode(s)

# string -> base64 encrypted string
def encrypt(s: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(s.encode(), salt)

    return encodeBase64(hashed)

# check if same between string(original) and base64 encrypted string
def checkSame(s: str, hashed: str) -> bool:
    return bcrypt.checkpw(s.encode(), decodeBase64(hashed))


if __name__ == '__main__':
    passwd = '123456'
    print(passwd)
    code = encrypt(passwd)
    print(code)
    print(type(code))
    print(checkSame('123456', code))
    print(checkSame('123', code))
