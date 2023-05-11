# -*- coding: utf-8 -*-
#br 从launcher.py跳过来
from jwt import decode

from ..openai.utils import Console

__public_key = b'-----BEGIN PUBLIC KEY-----\n' \
               b'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA27rOErDOPvPc3mOADYtQ\n' \
               b'BeenQm5NS5VHVaoO/Zmgsf1M0Wa/2WgLm9jX65Ru/K8Az2f4MOdpBxxLL686ZS+K\n' \
               b'7eJC/oOnrxCRzFYBqQbYo+JMeqNkrCn34yed4XkX4ttoHi7MwCEpVfb05Qf/ZAmN\n' \
               b'I1XjecFYTyZQFrd9LjkX6lr05zY6aM/+MCBNeBWp35pLLKhiq9AieB1wbDPcGnqx\n' \
               b'lXuU/bLgIyqUltqLkr9JHsf/2T4VrXXNyNeQyBq5wjYlRkpBQDDDNOcdGpx1buRr\n' \
               b'Z2hFyYuXDRrMcR6BQGC0ur9hI5obRYlchDFhlb0ElsJ2bshDDGRk5k3doHqbhj2I\n' \
               b'gQIDAQAB\n' \
               b'-----END PUBLIC KEY-----'


def check_access_token(access_token, api=False):
    '''验证给定的访问令牌是否有效
    1. 检查访问令牌是否以 'sk-' 开头
        - 如果是，立即返回 `True`，结束函数。
    2. 解码访问令牌
        - 使用 `decode` 函数，将 `access_token` 解码为一个负载 (`payload`)。这个过程中会验证令牌的签名，确保令牌是由一个信任的发行者签发的。
    3. 检查解码后的负载是否包含 'scope' 键
        - 如果不包含，抛出一个异常，结束函数。
    4. 检查 'scope' 键对应的值是否包含 'model.read' 和 'model.request'
        - 如果不包含，抛出一个异常，结束函数。
    5. 返回解码后的负载
        - 如果所有检查都通过，函数将返回解码后的负载。这是函数的最终输出，可以被调用者用来获取访问令牌的详情。
    '''
    if api and access_token.startswith('sk-'):
        return True
    #br 与官方检查token
    payload = (decode(access_token, key=__public_key, algorithms='RS256', audience=[
        "https://api.openai.com/v1",
        "https://openai.openai.auth0app.com/userinfo"
    ], issuer='https://auth0.openai.com/'))

    if 'scope' not in payload:
        raise Exception('miss scope')

    scope = payload['scope']
    if 'model.read' not in scope or 'model.request' not in scope:
        raise Exception('invalid scope')

    return payload


def check_access_token_out(access_token, api=False):
    try:
        return check_access_token(access_token, api)
    except Exception as e:
        Console.error('### Invalid access token: {}'.format(str(e)))
        return False
