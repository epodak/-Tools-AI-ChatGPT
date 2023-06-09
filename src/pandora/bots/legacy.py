# -*- coding: utf-8 -*-
#br 从launcher.py跳转进来的
import re
import uuid

import pyperclip
from rich.prompt import Prompt, Confirm

from .. import __version__
from ..openai.utils import Console


class ChatPrompt:
    def __init__(self, prompt: str = None, parent_id=None, message_id=None):
        #br 接收用户的prompt
        self.prompt = prompt
        self.parent_id = parent_id or self.gen_message_id()
        self.message_id = message_id or self.gen_message_id()

    @staticmethod
    def gen_message_id():
        return str(uuid.uuid4())


class State:
    def __init__(self, title=None, conversation_id=None, model_slug=None, user_prompt=ChatPrompt(),
                 chatgpt_prompt=ChatPrompt()):
        self.title = title
        self.conversation_id = conversation_id
        self.model_slug = model_slug
        self.user_prompt = user_prompt
        self.chatgpt_prompt = chatgpt_prompt
        self.user_prompts = []
        self.edit_index = None


class ChatBot:
    def __init__(self, chatgpt):
        self.chatgpt = chatgpt
        self.token_key = None
        self.state = None

    def run(self):
        self.token_key = self.__choice_token_key()
        #br 导出会话历史
        conversation_base = self.__choice_conversation()
        if conversation_base:
            self.__load_conversation(conversation_base['id'])
        else:
            self.__new_conversation()

        self.__talk_loop()

    def __talk_loop(self):
        #br 开始循环对话的地方
        while True:
            Console.info_b('You{}:'.format(' (edit)' if self.state and self.state.edit_index else ''))

            prompt = self.__get_input()
            if not prompt:
                continue

            if '/' == prompt[0]:
                self.__process_command(prompt)
                continue

            self.__talk(prompt)

    @staticmethod
    def __get_input():
        lines = []
        #br 从用户输入获取内容，做两次停留第一次是判断是否有指令，第二次是判断是否回车结束

        while True:
            line = input()

            if not line:
                break

            if '/' == line[0]:
                return line

            lines.append(line)

        return '\n'.join(lines)

    def __process_command(self, command):
        command = command.strip().lower()

        if '/quit' == command or '/exit' == command or '/bye' == command:
            raise KeyboardInterrupt
        elif '/del' == command or '/delete' == command or '/remove' == command:
            self.__del_conversation(self.state)
        elif '/title' == command or '/set_title' == command or '/set-title' == command:
            self.__set_conversation_title(self.state)
        elif '/select' == command:
            self.run()
        elif '/refresh' == command or '/reload' == command:
            self.__load_conversation(self.state.conversation_id)
        elif '/new' == command:
            self.__new_conversation()
            self.__talk_loop()
        elif '/regen' == command or '/regenerate' == command:
            self.__regenerate_reply(self.state)
        elif '/goon' == command or '/continue' == command:
            self.__continue(self.state)
        elif '/edit' == command or '/modify' == command:
            self.__edit_choice()
        elif '/token' == command:
            self.__print_access_token()
        elif '/cls' == command or '/clear' == command:
            self.__clear_screen()
        elif '/copy' == command or '/cp' == command:
            self.__copy_text()
        elif '/copy_code' == command or "/cp_code" == command:
            self.__copy_code()
        elif '/ver' == command or '/version' == command:
            self.__print_version()
        else:
            self.__print_usage()

    @staticmethod
    def __print_usage():
        Console.info_b('\n#### Command list:')
        print('/?\t\tShow this help message.')
        print('/title\t\tSet the current conversation\'s title.')
        print('/select\t\tChoice a different conversation.')
        print('/reload\t\tReload the current conversation.')
        print('/regen\t\tRegenerate response.')
        print('/continue\t\tContinue generating.')
        print('/edit\t\tEdit one of your previous prompt.')
        print('/new\t\tStart a new conversation.')
        print('/del\t\tDelete the current conversation.')
        print('/token\t\tPrint your access token.')
        print('/copy\t\tCopy the last response to clipboard.')
        print('/copy_code\t\tCopy code from last response.')
        print('/clear\t\tClear your screen.')
        print('/version\tPrint the version of Pandora.')
        print('/exit\t\tExit Pandora.')
        print()

    def __edit_choice(self):
        if not self.state.user_prompts:
            return

        choices = []
        pattern = re.compile(r'\s+')
        Console.info_b('Choice your prompt to edit:')
        for idx, item in enumerate(self.state.user_prompts):
            number = str(idx + 1)
            choices.append(number)

            preview_prompt = re.sub(pattern, ' ', item.prompt)
            if len(preview_prompt) > 40:
                preview_prompt = '{}...'.format(preview_prompt[0:40])

            Console.info('  {}.\t{}'.format(number, preview_prompt))

        choices.append('c')
        Console.warn('  c.\t** Cancel')

        default_choice = None if len(choices) > 2 else '1'
        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False, default=default_choice)
            if 'c' == choice:
                return

            self.state.edit_index = int(choice)
            return

    def __print_access_token(self):
        Console.warn_b('\n#### Your access token (keep it private)')
        Console.warn(self.chatgpt.get_access_token(token_key=self.token_key))
        print()

    def __clear_screen(self):
        Console.clear()

        if self.state:
            self.__print_conversation_title(self.state.title)

    @staticmethod
    def __print_version():
        Console.debug_bh('#### Version: {}'.format(__version__))
        print()

    def __new_conversation(self):
        self.state = State(model_slug=self.__choice_model()['slug'])

        self.state.title = 'New Chat'
        self.__print_conversation_title(self.state.title)

    @staticmethod
    def __print_conversation_title(title: str):
        Console.info_bh('==================== {} ===================='.format(title))
        Console.debug_h('Double enter to send. Type /? for help.')

    def __set_conversation_title(self, state: State):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        new_title = Prompt.ask('New title')
        if len(new_title) > 64:
            Console.error('#### Title too long.')
            return

        if self.chatgpt.set_conversation_title(state.conversation_id, new_title, token=self.token_key):
            state.title = new_title
            Console.debug('#### Set title success.')
        else:
            Console.error('#### Set title failed.')

    def __clear_conversations(self):
        if not Confirm.ask('Are you sure?', default=False):
            return

        if self.chatgpt.clear_conversations(token=self.token_key):
            self.run()
        else:
            Console.error('#### Clear conversations failed.')

    def __del_conversation(self, state: State):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        if not Confirm.ask('Are you sure?', default=False):
            return

        if self.chatgpt.del_conversation(state.conversation_id, token=self.token_key):
            self.run()
        else:
            Console.error('#### Delete conversation failed.')

    def __load_conversation(self, conversation_id):
        """ 加载指定的对话，并将对话内容以逆序方式展示出来。
        1. 检查传入的 conversation_id，如果为空则直接返回。
        2. 创建 State 实例，将 conversation_id 存储在其中。
        3. 通过 chatgpt 的 get_conversation 方法获取指定 ID 的对话内容。
        4. 通过 while 循环将对话内容按照父子关系进行反向排序，将整个对话内容从开始到结束存储在 nodes 列表中。
        5. 设置 State 实例的 title 属性，并打印对话的标题。
        6. 遍历 nodes 列表，处理每一条对话内容。如果对话的角色是用户或者助手，则分别处理，并打印对话内容。如果对话的角色既不是用户也不是助手，则跳过当前对话内容。
        7. 对每一条对话内容，设置相应的 prompt 属性，并设置其 parent_id 和 message_id。
        8. 如果当前对话内容不是合并的内容，则打印一个空行，以分隔不同的对话内容。
        """

        if not conversation_id:
            return
        #br 加载对话
        self.state = State(conversation_id=conversation_id)

        nodes = []
        result = self.chatgpt.get_conversation(conversation_id, token=self.token_key)
        current_node_id = result['current_node']

        while True:
            node = result['mapping'][current_node_id]
            if not node.get('parent'):
                break

            nodes.insert(0, node)
            current_node_id = node['parent']

        self.state.title = result['title']
        #br 可能是打印对话
        self.__print_conversation_title(self.state.title)

        merge = False
        for node in nodes:
            message = node['message']
            if 'model_slug' in message['metadata']:
                self.state.model_slug = message['metadata']['model_slug']

            role = message['author']['role'] if 'author' in message else message['role']

            if 'user' == role:
                prompt = self.state.user_prompt
                self.state.user_prompts.append(ChatPrompt(message['content']['parts'][0], parent_id=node['parent']))

                Console.info_b('You:')
                Console.info(message['content']['parts'][0])
            elif 'assistant' == role:
                prompt = self.state.chatgpt_prompt

                if not merge:
                    Console.success_b('ChatGPT:')
                Console.success(message['content']['parts'][0])

                merge = 'end_turn' in message and message['end_turn'] is None
            else:
                continue

            prompt.prompt = message['content']['parts'][0]
            prompt.parent_id = node['parent']
            prompt.message_id = node['id']
            #br 这地方可能是gpt流式输出的开始
            if not merge:
                print()

    def __talk(self, prompt):
        Console.success_b('ChatGPT:')
        #br 对用户的对话开始发送给ChatGPT
        first_prompt = not self.state.conversation_id

        if self.state.edit_index:
            idx = self.state.edit_index - 1
            user_prompt = self.state.user_prompts[idx]
            self.state.user_prompt = ChatPrompt(prompt, parent_id=user_prompt.parent_id)
            #br 这地方可能是流式输出发送对话
            self.state.user_prompts = self.state.user_prompts[0:idx]

            self.state.edit_index = None
        else:
            self.state.user_prompt = ChatPrompt(prompt, parent_id=self.state.chatgpt_prompt.message_id)
        #br 流式输出结束
        status, _, generator = self.chatgpt.talk(prompt, self.state.model_slug, self.state.user_prompt.message_id,
                                                 self.state.user_prompt.parent_id, self.state.conversation_id,
                                                 token=self.token_key)
        self.__print_reply(status, generator)

        self.state.user_prompts.append(self.state.user_prompt)

        if first_prompt:
            new_title = self.chatgpt.gen_conversation_title(self.state.conversation_id, self.state.model_slug,
                                                            self.state.chatgpt_prompt.message_id, token=self.token_key)
            self.state.title = new_title
            Console.debug_bh('#### Title generated: ' + new_title)

    def __regenerate_reply(self, state):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        status, _, generator = self.chatgpt.regenerate_reply(state.user_prompt.prompt, state.model_slug,
                                                             state.conversation_id, state.user_prompt.message_id,
                                                             state.user_prompt.parent_id, token=self.token_key)
        print()
        Console.success_b('ChatGPT:')
        self.__print_reply(status, generator)

    def __continue(self, state):
        if not state.conversation_id:
            Console.error('#### Conversation has not been created.')
            return

        status, _, generator = self.chatgpt.goon(state.model_slug, state.chatgpt_prompt.message_id,
                                                 state.conversation_id, token=self.token_key)
        print()
        Console.success_b('ChatGPT:')
        self.__print_reply(status, generator)

    def __print_reply(self, status, generator):
        #br 这地方开始打印流式输出，这地方一个字一个字的蹦
        if 200 != status:
            raise Exception(status, next(generator))

        p = 0
        for result in generator:
            if result['error']:
                raise Exception(result['error'])

            if not result['message']:
                raise Exception('miss message property.')

            text = None
            message = result['message']
            if 'assistant' == message['author']['role']:
                text = message['content']['parts'][0][p:]
                p += len(text)

            self.state.conversation_id = result['conversation_id']
            self.state.chatgpt_prompt.prompt = message['content']['parts'][0]
            self.state.chatgpt_prompt.parent_id = self.state.user_prompt.message_id
            self.state.chatgpt_prompt.message_id = message['id']

            if 'system' == message['author']['role']:
                self.state.user_prompt.parent_id = message['id']

            if text:
                Console.success(text, end='')

        print('\n')

    def __choice_conversation(self, page=1, page_size=20):
        #br 让用户选择id
        conversations = self.chatgpt.list_conversations((page - 1) * page_size, page_size, token=self.token_key)
        if not conversations['total']:
            return None

        choices = ['c', 'r', 'dd']
        items = conversations['items']
        first_page = 0 == conversations['offset']
        last_page = (conversations['offset'] + conversations['limit']) >= conversations['total']

        Console.info_b('Choice conversation (Page {}):'.format(page))
        #br 这里就是后台返回循环查询的对话的数据
        for idx, item in enumerate(items):
            number = str(idx + 1)
            choices.append(number)
            choices.append('t' + number)
            choices.append('d' + number)
            Console.info('  {}.\t{}'.format(number, item['title'].replace('\n', ' ')))

        if not last_page:
            choices.append('n')
            Console.warn('  n.\t>> Next page')

        if not first_page:
            choices.append('p')
            Console.warn('  p.\t<< Previous page')

        Console.warn('  t?.\tSet title for the conversation, eg: t1')
        Console.warn('  d?.\tDelete the conversation, eg: d1')
        Console.warn('  dd.\t!! Clear all conversations')
        Console.warn('  r.\tRefresh conversation list')

        if len(self.chatgpt.list_token_keys()) > 1:
            choices.append('k')
            Console.warn('  k.\tChoice access token')

        Console.warn('  c.\t** Start new chat')
        #br 这地方让用户开始选择
        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False)
            if 'c' == choice:
                return None

            if 'k' == choice:
                self.run()
                return

            if 'r' == choice:
                return self.__choice_conversation(page, page_size)

            if 'n' == choice:
                return self.__choice_conversation(page + 1, page_size)

            if 'p' == choice:
                return self.__choice_conversation(page - 1, page_size)

            if 'dd' == choice:
                self.__clear_conversations()
                continue

            if 't' == choice[0]:
                self.__set_conversation_title(State(conversation_id=items[int(choice[1:]) - 1]['id']))
                return self.__choice_conversation(page, page_size)

            if 'd' == choice[0]:
                self.__del_conversation(State(conversation_id=items[int(choice[1:]) - 1]['id']))
                continue

            return items[int(choice) - 1]

    def __choice_token_key(self):
        tokens = self.chatgpt.list_token_keys()

        size = len(tokens)
        if 1 == size:
            return None

        choices = ['r']
        Console.info_b('Choice access token:')
        for idx, item in enumerate(tokens):
            number = str(idx + 1)
            choices.append(number)
            Console.info('  {}.\t{}'.format(number, item))

        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False)

            return tokens[int(choice) - 1]

    def __choice_model(self):
        models = self.chatgpt.list_models(token=self.token_key)

        size = len(models)
        if 1 == size:
            return models[0]

        choices = ['r']
        Console.info_b('Choice model:')
        for idx, item in enumerate(models):
            number = str(idx + 1)
            choices.append(number)
            Console.info('  {}.\t{} - {}'.format(number, item['title'], item['description']))

        Console.warn('  r.\tRefresh model list')

        while True:
            choice = Prompt.ask('Your choice', choices=choices, show_choices=False)
            if 'r' == choice:
                return self.__choice_model()

            return models[int(choice) - 1]

    def __copy_text(self):
        pyperclip.copy(self.state.chatgpt_prompt.prompt)
        Console.info("已将上一次返回结果复制到剪切板。")
        pass

    def __copy_code(self):
        text = self.state.chatgpt_prompt.prompt
        pattern = re.compile(r'```.*\s([\s\S]*?)\s```')
        result = re.findall(pattern, text)
        if len(result) == 0:
            Console.info("未找到代码。")
            return
        else:
            code = '\n=======================================================\n'.join(result)
            pyperclip.copy(code)
            Console.info("已将上一次生成的代码复制到剪切板。")
        pass
