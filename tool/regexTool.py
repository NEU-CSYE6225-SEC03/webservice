import re


def isValidEmail(s: str):
    pattern = r'^[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+){0,4}@[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+){0,4}$'
    if re.match(pattern=pattern, string=s):
        return True
    else:
        return False


if __name__ == '__main__':
    s = 'lai.we@gmail.com'
    print(isValidEmail(s))
    s = '666@outlook.com'
    print(isValidEmail(s))
    s = '@neu.edu'
    print(isValidEmail(s))
