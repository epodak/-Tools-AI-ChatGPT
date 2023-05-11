# -*- coding: utf-8 -*-
#br 这个是从server.py 跳过来的
import asyncio
import json
import queue as block_queue
import threading
from os import getenv

import httpx
import requests
from certifi import where

from .. import __version__


class API:
    def __init__(self, proxy, ca_bundle):
        self.proxy = proxy
        self.ca_bundle = ca_bundle

    @staticmethod
    def wrap_stream_out(generator, status):
        if status != 200:
            for line in generator:
                yield json.dumps(line)

            return

        for line in generator:
            yield b'data: ' + json.dumps(line).encode('utf-8') + b'\n\n'

        yield b'data: [DONE]\n\n'

    async def __process_sse(self, resp):
        yield resp.status_code
        yield resp.headers

        if resp.status_code != 200:
            yield await self.__process_sse_except(resp)
            return

        async for utf8_line in resp.aiter_lines():
            if 'data: [DONE]' == utf8_line[0:12]:
                break

            if 'data: {' == utf8_line[0:7]:
                yield json.loads(utf8_line[6:])

    @staticmethod
    async def __process_sse_except(resp):
        result = b''
        async for line in resp.aiter_bytes():
            result += line

        return json.loads(result.decode('utf-8'))

    @staticmethod
    def __generate_wrap(queue, thread, event):
        while True:
            #br 可能是对gpt的回答进行编码处理
            try:
                item = queue.get()
                if item is None:
                    break

                yield item
            except BaseException as e:
                event.set()
                thread.join()

                if isinstance(e, GeneratorExit):
                    raise e

    async def _do_request_sse(self, url, headers, data, queue, event):
        async with httpx.AsyncClient(verify=self.ca_bundle, proxies=self.proxy) as client:
            async with client.stream('POST', url, json=data, headers=headers, timeout=600) as resp:
                async for line in self.__process_sse(resp):
                    queue.put(line)

                    if event.is_set():
                        await client.aclose()
                        break

                queue.put(None)

    def _request_sse(self, url, headers, data):
        #br 这地方是队列获取，可能是流式输出的开始
        queue, e = block_queue.Queue(), threading.Event()
        t = threading.Thread(target=asyncio.run, args=(self._do_request_sse(url, headers, data, queue, e),))
        t.start()

        return queue.get(), queue.get(), self.__generate_wrap(queue, t, e)


class ChatGPT(API):
    def __init__(self, access_tokens: dict, proxy=None):
        #br API post通讯
        self.access_tokens = access_tokens
        self.access_token_key_list = list(access_tokens)
        self.default_token_key = self.access_token_key_list[0]
        self.session = requests.Session()
        self.req_kwargs = {
            'proxies': {
                'http': proxy,
                'https': proxy,
            } if proxy else None,
            'verify': where(),
            'timeout': 100,
            'allow_redirects': False,
        }

        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                          'Pandora/{} Safari/537.36'.format(__version__)

        self.api_prefix = getenv('CHATGPT_API_PREFIX', 'https://ai.fakeopen.com')

        super().__init__(proxy, self.req_kwargs['verify'])

    def __get_headers(self, token_key=None):
        return {
            'Authorization': 'Bearer ' + self.get_access_token(token_key),
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
        }

    def get_access_token(self, token_key=None):
        return self.access_tokens[token_key or self.default_token_key]

    def list_token_keys(self):
        return self.access_token_key_list

    def list_models(self, raw=False, token=None):
        url = '{}/api/models'.format(self.api_prefix)
        resp = self.session.get(url=url, headers=self.__get_headers(token), **self.req_kwargs)

        if raw:
            return resp

        if resp.status_code != 200:
            raise Exception('list models failed: ' + self.__get_error(resp))

        result = resp.json()
        if 'models' not in result:
            raise Exception('list models failed: ' + resp.text)

        return result['models']

    def list_conversations(self, offset, limit, raw=False, token=None):
        #br 列出对话ID
        url = '{}/api/conversations?offset={}&limit={}'.format(self.api_prefix, offset, limit)
        resp = self.session.get(url=url, headers=self.__get_headers(token), **self.req_kwargs)

        if raw:
            return resp

        if resp.status_code != 200:
            raise Exception('list conversations failed: ' + self.__get_error(resp))

        return resp.json()

    def get_conversation(self, conversation_id, raw=False, token=None):
        """ 从服务器上获取指定的对话内容。
        1. 构造 API 请求的 URL，URL 中包含了 API 的前缀和对话 ID。
        2. 通过 session 的 get 方法发送 GET 请求到服务器，请求的 URL 就是第一步中构造的 URL，请求头中包含了 token 信息。
            self.session.get: 这是一个使用 requests 库的 session 对象的 GET 方法。这个方法会发送一个 HTTP GET 请求到指定的 URL。
            url=url: 这是一个关键字参数，指定了请求的 URL。这个 URL 是 API 的地址，加上 conversation_id 构成的。
            headers=self.__get_headers(token): 这是另一个关键字参数，它设置了 HTTP 请求的头部信息。self.__get_headers(token) 是一个私有方法，它返回一个包含认证信息的字典。这个字典将被用作 HTTP 请求的头部。
            **self.req_kwargs: 这是一种在 Python 中传递关键字参数的方式，叫做解包操作。self.req_kwargs 是一个字典，它可能包含了其他一些额外的关键字参数，这些参数会被传递给 get 方法。这样做的好处是，如果有其他需要添加到请求中的参数，可以方便地将它们添加到 self.req_kwargs 字典中，而不需要修改这行代码。
        3. 检查参数 raw，如果 raw 为 True，那么直接返回服务器的响应内容。
        4. 检查服务器响应的状态码，如果状态码不是 200，那么表示请求失败，抛出异常。
        5. 如果请求成功，那么返回服务器响应的 JSON 内容。
        """
        
        #br 获取对话
        url = '{}/api/conversation/{}'.format(self.api_prefix, conversation_id)
        resp = self.session.get(url=url, headers=self.__get_headers(token), **self.req_kwargs)

        if raw:
            return resp

        if resp.status_code != 200:
            raise Exception('get conversation failed: ' + self.__get_error(resp))

        return resp.json()

    def clear_conversations(self, raw=False, token=None):
        data = {
            'is_visible': False,
        }

        url = '{}/api/conversations'.format(self.api_prefix)
        resp = self.session.patch(url=url, headers=self.__get_headers(token), json=data, **self.req_kwargs)

        if raw:
            return resp

        if resp.status_code != 200:
            raise Exception('clear conversations failed: ' + self.__get_error(resp))

        result = resp.json()
        if 'success' not in result:
            raise Exception('clear conversations failed: ' + resp.text)

        return result['success']

    def del_conversation(self, conversation_id, raw=False, token=None):
        data = {
            'is_visible': False,
        }

        return self.__update_conversation(conversation_id, data, raw, token)

    def gen_conversation_title(self, conversation_id, model, message_id, raw=False, token=None):
        url = '{}/api/conversation/gen_title/{}'.format(self.api_prefix, conversation_id)
        data = {
            'model': model,
            'message_id': message_id,
        }
        resp = self.session.post(url=url, headers=self.__get_headers(token), json=data, **self.req_kwargs)

        if raw:
            return resp

        if resp.status_code != 200:
            raise Exception('gen title failed: ' + self.__get_error(resp))

        result = resp.json()
        if 'title' not in result:
            raise Exception('gen title failed: ' + resp.text)

        return result['title']

    def set_conversation_title(self, conversation_id, title, raw=False, token=None):
        data = {
            'title': title,
        }

        return self.__update_conversation(conversation_id, data, raw, token)

    def talk(self, prompt, model, message_id, parent_message_id, conversation_id=None, stream=True, token=None):
        data = {
            #br 将用户的prompt打包
            'action': 'next',
            'messages': [
                {
                    'id': message_id,
                    'role': 'user',
                    'author': {
                        'role': 'user',
                    },
                    'content': {
                        'content_type': 'text',
                        'parts': [prompt],
                    },
                }
            ],
            'model': model,
            'parent_message_id': parent_message_id,
        }

        if conversation_id:
            data['conversation_id'] = conversation_id
        #br 返回gpt答案
        return self.__request_conversation(data, token)

    def goon(self, model, parent_message_id, conversation_id, stream=True, token=None):
        data = {
            'action': 'continue',
            'conversation_id': conversation_id,
            'model': model,
            'parent_message_id': parent_message_id,
        }

        return self.__request_conversation(data, token)

    def regenerate_reply(self, prompt, model, conversation_id, message_id, parent_message_id, stream=True, token=None):
        data = {
            'action': 'variant',
            'messages': [
                {
                    'id': message_id,
                    'role': 'user',
                    'author': {
                        'role': 'user',
                    },
                    'content': {
                        'content_type': 'text',
                        'parts': [prompt],
                    },
                }
            ],
            'model': model,
            'conversation_id': conversation_id,
            'parent_message_id': parent_message_id,
        }

        return self.__request_conversation(data, token)

    def __request_conversation(self, data, token=None):
        #br 获取gpt对话
        url = '{}/api/conversation'.format(self.api_prefix)
        headers = {**self.session.headers, **self.__get_headers(token), 'Accept': 'text/event-stream'}

        return self._request_sse(url, headers, data)

    def __update_conversation(self, conversation_id, data, raw=False, token=None):
        url = '{}/api/conversation/{}'.format(self.api_prefix, conversation_id)
        resp = self.session.patch(url=url, headers=self.__get_headers(token), json=data, **self.req_kwargs)

        if raw:
            return resp

        if resp.status_code != 200:
            raise Exception('update conversation failed: ' + self.__get_error(resp))

        result = resp.json()
        if 'success' not in result:
            raise Exception('update conversation failed: ' + resp.text)

        return result['success']

    @staticmethod
    def __get_error(resp):
        try:
            return str(resp.json()['detail'])
        except:
            return resp.text


class ChatCompletion(API):
    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.req_kwargs = {
            'proxies': {
                'http': proxy,
                'https': proxy,
            } if proxy else None,
            'verify': where(),
            'timeout': 600,
            'allow_redirects': False,
        }

        self.user_agent = 'pandora/{}'.format(__version__)

        super().__init__(proxy, self.req_kwargs['verify'])

    def __get_headers(self, api_key):
        return {
            'Authorization': 'Bearer ' + api_key,
            'User-Agent': self.user_agent,
            'Content-Type': 'application/json',
        }

    def request(self, api_key, model, messages, stream=True, **kwargs):
        data = {
            'model': model,
            'messages': messages,
            **kwargs,
            'stream': stream,
        }

        return self.__request_conversation(api_key, data, stream)

    def __request_conversation(self, api_key, data, stream):
        url = '{}/v1/chat/completions'.format(getenv('OPENAI_API_PREFIX', 'https://api.openai.com'))

        if stream:
            headers = {**self.__get_headers(api_key), 'Accept': 'text/event-stream'}
            return self._request_sse(url, headers, data)

        resp = self.session.post(url=url, headers=self.__get_headers(api_key), json=data, **self.req_kwargs)

        def __generate_wrap():
            yield resp.json()

        return resp.status_code, resp.headers, __generate_wrap()
