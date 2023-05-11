# -*- coding: utf-8 -*-
#br 从__main__.py过来的一个代码，前面是__init__.py
import argparse
import os
from os import getenv

from loguru import logger
from rich.prompt import Prompt, Confirm

from . import __version__
from .bots.legacy import ChatBot as ChatBotLegacy
from .bots.server import ChatBot as ChatBotServer
from .exts import sentry
from .exts.config import USER_CONFIG_DIR
from .exts.hooks import hook_except_handle
from .exts.token import check_access_token_out
from .openai.api import ChatGPT
from .openai.auth import Auth0
from .openai.utils import Console

if 'nt' == os.name:
    import pyreadline3 as readline
else:
    import readline

    readline.set_completer_delims('')
    readline.set_auto_history(False)

__show_verbose = False


def read_access_token(token_file):
    with open(token_file, 'r') as f:
        return f.read().strip()


def save_access_token(access_token):
    token_file = os.path.join(USER_CONFIG_DIR, 'access_token.dat')

    if not os.path.exists(USER_CONFIG_DIR):
        os.makedirs(USER_CONFIG_DIR)

    with open(token_file, 'w') as f:
        f.write(access_token)

    if __show_verbose:
        Console.debug_b('\nThe access token has been saved to the file:')
        Console.debug(token_file)
        print()


def confirm_access_token(token_file=None, silence=False, api=False):
    app_token_file = os.path.join(USER_CONFIG_DIR, 'access_token.dat')

    app_token_file_exists = os.path.isfile(app_token_file)
    if app_token_file_exists and __show_verbose:
        Console.debug_b('Found access token file: ', end='')
        Console.debug(app_token_file)

    if token_file:
        if not os.path.isfile(token_file):
            raise Exception('Error: {} is not a file.'.format(token_file))

        access_token = read_access_token(token_file)
        if os.path.isfile(app_token_file) and access_token == read_access_token(app_token_file):
            return access_token, False

        return access_token, True
    #br 如涉及到这一步，默认使用已存储的token，此处输入y并回车
    if app_token_file_exists:
        confirm = 'y' if silence else Prompt.ask('A saved access token has been detected. Do you want to use it?',
                                                 choices=['y', 'n', 'del'], default='y')
        if 'y' == confirm:
            access_token = read_access_token(app_token_file)
            if not check_access_token_out(access_token, api):
                os.remove(app_token_file)
                return None, True

            return access_token, False
        elif 'del' == confirm:
            os.remove(app_token_file)

    return None, True


def parse_access_tokens(tokens_file, api=False):
    if not os.path.isfile(tokens_file):
        raise Exception('Error: {} is not a file.'.format(tokens_file))

    import json
    with open(tokens_file, 'r') as f:
        tokens = json.load(f)

    valid_tokens = {}
    for key, value in tokens.items():
        if not check_access_token_out(value, api=api):
            Console.error('### Access token id: {}'.format(key))
            continue
        valid_tokens[key] = value

    if not valid_tokens:
        Console.error('### No valid access tokens.')
        return None

    return valid_tokens

#br 主函数入口
def main():
    """ `main`函数为Pandora CLI工具提供入口，解析命令行参数并初始化ChatGPT对话系统。根据参数设置，可以选择以API方式或代理服务器方式运行。
    1. 设置全局的 verbose 标志，用于确定是否显示详细的错误跟踪信息。
    2. 从环境变量获取并设置 API 前缀，然后显示一些基本信息，如获取访问令牌的 URL 和当前的版本号。
    3. 通过argparse库解析命令行参数。
    - 这里设置了一系列的选项，包括代理设置、访问令牌文件、服务器模式、API 模式、错误报告、详细输出等。
    4. 根据解析得到的参数进行一系列的初始化工作。
    - 如果启用了 sentry 错误报告，就初始化 sentry。
    - 如果启用了 API 模式，尝试导入相关的模块，并执行数据库迁移。
    5. 尝试从文件中解析访问令牌。如果没有指定文件，或者文件中没有有效的访问令牌，就让用户手动输入并验证。
    - 通过 Auth0 进行身份验证，并获取访问令牌。
    - 如果需要，保存访问令牌以供下次使用。
    6. 根据参数创建相应的 ChatGPT 实例。如果是 API 模式，就创建 TurboGPT，否则就创建普通的 ChatGPT。
    7. 根据参数运行相应的对话系统。如果是服务器模式，就运行 ChatBotServer，否则就运行 ChatBotLegacy。
    """
    global __show_verbose
    #br 这是函数第一行，如果要进入这个函数断点应该打在这里
    api_prefix = getenv('CHATGPT_API_PREFIX', 'https://ai.fakeopen.com')

    Console.debug_b(
        '''
            Pandora - A command-line interface to ChatGPT
            Github: https://github.com/pengzhile/pandora
            Get access token: {}/auth
            Version: {}'''.format(api_prefix, __version__), end=''
            # end 是作为关键字参数传递给 Console.debug_b 函数的。
            # 在 Python 中，print() 函数有一个 end 参数，它用于指定字符串末尾的内容。默认情况下，end 的值为 '\n'，这意味着在打印完字符串后，会自动添加一个换行符。
    )
    #br CLI中的命令参数例如 -t 就是输入token地址
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-p',
        '--proxy',
        help='Use a proxy. Format: protocol://user:pass@ip:port',
        required=False,
        type=str,
        default=None,
    )
    parser.add_argument(
        '-t',
        '--token_file',
        help='Specify an access token file and login with your access token.',
        required=False,
        type=str,
        default=None,
    )
    parser.add_argument(
        '--tokens_file',
        help='Specify an access tokens json file.',
        required=False,
        type=str,
        default=None,
    )
    parser.add_argument(
        '-s',
        '--server',
        help='Start as a proxy server. Format: ip:port, default: 127.0.0.1:8008',
        required=False,
        type=str,
        default=None,
        action='store',
        nargs='?',
        const='127.0.0.1:8008',
    )
    parser.add_argument(
        '--threads',
        help='Define the number of server workers, default: 8',
        required=False,
        type=int,
        default=8,
    )
    parser.add_argument(
        '-a',
        '--api',
        help='Use gpt-3.5-turbo chat api. Note: OpenAI will bill you.',
        action='store_true',
    )
    parser.add_argument(
        '--sentry',
        help='Enable sentry to send error reports when errors occur.',
        action='store_true',
    )
    parser.add_argument(
        '-v',
        '--verbose',
        help='Show exception traceback.',
        action='store_true',
    )
    args, _ = parser.parse_known_args()
    __show_verbose = args.verbose

    Console.debug_b(''', Mode: {}, Engine: {}
        '''.format('server' if args.server else 'cli', 'turbo' if args.api else 'free'))

    if args.sentry:
        sentry.init(args.proxy)

    if args.api:
        try:
            from .openai.token import gpt_num_tokens
            from .migrations.migrate import do_migrate

            do_migrate()
        except (ImportError, ModuleNotFoundError):
            Console.error_bh('### You need `pip install Pandora-ChatGPT[api]` to support API mode.')
            return
    #br 这是后面的函数第一行，如检查token是否过期
    access_tokens = parse_access_tokens(args.tokens_file, args.api) if args.tokens_file else None

    # 如果 access_tokens 是 None 或者是其它表示假值的内容（如空字符串，空列表，0等），那么就执行这个条件块的代码。
    if not access_tokens:
        access_token, need_save = confirm_access_token(args.token_file, args.server, args.api)
        if not access_token:
            Console.info_b('Please enter your email and password to log in ChatGPT!')
            email = getenv('OPENAI_EMAIL') or Prompt.ask('  Email')
            password = getenv('OPENAI_PASSWORD') or Prompt.ask('  Password', password=True)
            Console.warn('### Do login, please wait...')
            access_token = Auth0(email, password, args.proxy).auth(True)

        if not check_access_token_out(access_token, args.api):
            return

        if need_save:
            if args.server or Confirm.ask('Do you want to save your access token for the next login?', default=True):
                save_access_token(access_token)

        access_tokens = {'default': access_token}

    if args.api:
        from .turbo.chat import TurboGPT

        chatgpt = TurboGPT(access_tokens, args.proxy)
    else:
        chatgpt = ChatGPT(access_tokens, args.proxy)

    if args.server:
        return ChatBotServer(chatgpt, args.verbose, args.sentry).run(args.server, args.threads)

    ChatBotLegacy(chatgpt).run()

#br 加载程序入口
def run():
    hook_except_handle()

    try:
        main()
    except Exception as e:
        Console.error_bh('### Error occurred: ' + str(e))

        if __show_verbose:
            logger.exception('Exception occurred.')

        sentry.capture(e)
