from mcdreforged.api.all import *
import re
from typing import Callable
from queue import Queue
import threading
import time
import asyncio
import websockets
import websockets.server
import json
from datetime import datetime


# 定义 MCDR 插件元数据
PLUGIN_METADATA = {
    'id': 'msm',
    'version': '1.0.0',
    'name': 'MC Server Monitor',
    'description': 'A plugin for MC server data analysis and processing',
    'author': 'src_resources',
    'link': 'https://github.com',
    'dependencies': {
        'mcdreforged': '>=1.0.0'
    }
}


# 定义本 MCDR 插件的配置选项
class PluginConfig(Serializable):
    # 与远程网站服务器通信而监听的IP地址
    commIP: str = '127.0.0.1'
    # 与远程网站服务器通信而监听的端口号
    commPort: int = 8765
    # MC服务器数据同步线程（ServerMonitorThread）的轮询间隔（单位：ms）
    serverMonitorThreadInterval: int = 1000
    # 远程网站服务器联络线程（WebsocketThread）的轮询间隔（单位：ms）
    websocketThreadInterval: int = 1000


# 当从MC服务器收到函数执行结果时执行的回调
class MCFuncResultSchedule(object):
    def __init__(self, mc_func: str, args: dict, callback: Callable[[str, dict, int], None]):
        # MC函数名称
        self.mc_func: str = mc_func
        # MC函数的参数列表，为一个字典
        self.args: dict = args
        # 当MC函数执行完成时，触发该回调函数
        self.callback: Callable[[str, dict, int], None] = callback

    
    def execute(self, result: int) -> None:
        self.callback(self.mc_func, self.args, result)


# MC服务器上所记录的玩家数据的所有条目名称（均已去除'msm_'前缀）
PLAYER_DATA_ITEMS: list[str] = [
    # -----
    # 下列记分项为游戏自动更新。
    # -----

    # 死亡数
    'deathCount',
    # 击杀玩家数
    'playerKillCount',
    # 击杀数（包括玩家和生物）
    'totalKillCount',
    # 生命值（包括伤害吸收值）【只读】
    'health',
    # 经验值【只读】
    'xp',
    # 等级【只读】
    'level',
    # 饥饿值【只读】
    'food',
    # 空气值【只读】
    'air',
    # 护甲值【只读】
    'armor',

    # -----
    # 下列记分项游戏不会自动更新，需通过监听游戏状态进行手动更新。
    # -----

    # 放置方块数
    'placeBlockCount',
    # 破坏方块数
    'breakBlockCount',
    # 在线时长（以游戏刻为单位）
    # 注：受限于记分板数据类型（32位有符号整型），上限值为2,147,483,647，
    # 也就是最多只能记录约1242.76天的时长。
    'onlineTime'
]


# 服务器上的玩家数据
class PlayerData(object):
    def __init__(self):
        # 玩家名称
        self.name: str = ''

        # -----
        # 下列记分项为游戏自动更新。
        # -----

        # 死亡数
        self.deathCount: int = 0
        # 击杀玩家数
        self.playerKillCount: int = 0
        # 击杀数（包括玩家和生物）
        self.totalKillCount: int = 0
        # 生命值（包括伤害吸收值）【只读】
        self.health: int = 0
        # 经验值【只读】
        self.xp: int = 0
        # 等级【只读】
        self.level: int = 0
        # 饥饿值【只读】
        self.food: int = 0
        # 空气值【只读】
        self.air: int = 0
        # 护甲值【只读】
        self.armor: int = 0

        # -----
        # 下列记分项游戏不会自动更新，需通过监听游戏状态进行手动更新。
        # -----

        # 放置方块数
        self.placeBlockCount: int = 0
        # 破坏方块数
        self.breakBlockCount: int = 0
        # 在线时长（以游戏刻为单位）
        # 注：受限于记分板数据类型（32位有符号整型），上限值为2,147,483,647，
        # 也就是最多只能记录约1242.76天的时长。
        self.onlineTime: int = 0


# 用于时刻同步MC服务器数据的线程
class ServerMonitorThread(threading.Thread):
    def __init__(self, interval: int):
        super().__init__()
        self.name = 'ServerMonitorThread'
        self.stop_event = threading.Event()
        self.daemon = False # 本线程不是守护线程，以确保对于服务器数据同步的完整性

        # 本线程的轮询间隔（ms）
        self.interval: int = interval if interval > 0 else 1000 # 缺省值为1000ms


    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                # 先检查MC服务器是否已启动
                if psi.is_server_running():
                    # 定时执行MC函数，获取服务器数据
                    for player in online_players:
                        execute_msm_get_data(player,'msm_deathCount')
                        execute_msm_get_data(player,'msm_playerKillCount')
                        execute_msm_get_data(player,'msm_totalKillCount')
                        execute_msm_get_data(player,'msm_health')
                        execute_msm_get_data(player,'msm_xp')
                        execute_msm_get_data(player,'msm_level')
                        execute_msm_get_data(player,'msm_food')
                        execute_msm_get_data(player,'msm_air')
                        execute_msm_get_data(player,'msm_armor')
                        execute_msm_get_data(player,'msm_placeBlockCount')
                        execute_msm_get_data(player,'msm_breakBlockCount')
                        execute_msm_get_data(player,'msm_onlineTime')
            except Exception as ex:
                psi.logger.error(f'Error occurred while updating player data: {ex}')
            # 休眠一段时间
            time.sleep(float(self.interval) / 1000.0)


    def stop(self) -> None:
        self.stop_event.set()


"""
【MC Server Monitor 数据传输协议规范】

2024.9.9 19:50修改

一、websocket通信	

1.网站后端服务器向mc服务器发送命令：
以字符串形式发送指令
为json格式：
{
id: 本请求所对应的流水号，用于标识一个唯一请求用于后面数据回传,
instruction: ‘指令名称（小写下划线命名法）’
arguments: {
... 该指令附带的参数 ...
}
}
目前只有一种指令：get_all_players_data（获取所有玩家数据）

2.Mc服务器向网站后端发送数据：
类型为json格式，具体格式如下：
{
id: 之前请求时所用的流水号,
instruction：’all_players_data’
data:{
name(string 玩家姓名):
type(num 1击杀数 2死亡数 3在线时长……后续由mc插件开发者补充):
quantity(num 数量):
date(date精确到小时 且分钟数不过半就归零11:30-12:29都归为12:00)：
}}·
type的种类：
死亡数 deathCount
击杀玩家数 playerKillCount
击杀数（包括玩家和生物） totalKillCount
生命值（包括伤害吸收值）【只读】 health
经验值【只读】 xp
等级【只读】 level
饥饿值【只读】 food
空气值【只读】 air
护甲值【只读】 armor
放置方块数 placeBlockCount
破坏方块数 breakBlockCount
在线时长（以游戏刻为单位） onlineTime
如上为一条数据。
网站后端服务器向mc服务器发送命令后，mc服务器每次向网站后端服务器发送一条数据，直到所有数据发送完毕
"""


# 用于与远程网站服务器进行数据交流的线程
class WebsocketThread(threading.Thread):
    def __init__(self, interval: int, ip: str, port: int):
        super().__init__()
        self.name = 'WebsocketThread'
        self.stop_event = threading.Event()
        self.daemon = False # 本线程不是守护线程，以确保与远程网站服务器的交流不会被异常地中断

        # 本线程的轮询间隔（ms）
        self.interval: int = interval if interval > 0 else 1000 # 缺省值为1000ms
        # WebSocket 监听的IP地址
        self.ip: str = ip
        # WebSocket 监听的端口号
        self.port: int = port


    def run(self) -> None:
        # 因为 websockets 模块使用异步函数，所以提前切换到 asyncio 运行时
        asyncio.run(self.__async_run())
    

    async def __async_run(self) -> None:
        # 创建 websocket 服务器
        serve = websockets.server.serve(self.__websocket_echo, self.ip, self.port)
        # 在死循环内开始运行 websocket 服务器，出错了就重新启动，正常停止就退出死循环
        while True:
            try:
                async with serve:
                    while not self.stop_event.is_set():
                        # 若线程仍在运行，执行休眠挂起
                        await asyncio.sleep(float(self.interval) / 1000.0)
            except OSError as ex:
                psi.logger.error(f'Error occurred while starting the websocket server: {ex}')
                interval = float(self.interval) / 1000.0
                psi.logger.error(f'Retrying in {interval} seconds...')
                await asyncio.sleep(interval)
            else:
                # 服务器正常停止，退出死循环
                break
        
        psi.logger.info('The websocket thread is stopping...')

    
    async def __websocket_echo(self, websocket: websockets.WebSocketClientProtocol) -> None:
        iter = aiter(websocket)
        try:
            while not self.stop_event.is_set():
                message = await anext(iter)
                responses = await self.__process_message(message)
                for response in responses:
                    await websocket.send(response)
            psi.logger.info(f'The websocket thread is stopping, consequently closing the existing ' +
                            f'websocket connection with remote server {websocket.host}:{websocket.port}...')
        except Exception as ex:
            psi.logger.error(f'Error occurred while echoing data to remote server {websocket.host}:{websocket.port}: {ex}')
        finally:
            await websocket.close()


    async def __process_message(self, message: str | bytes) -> list[str]:
        """
        处理来自客户端的JSON请求信息，并返回将要回传给客户端的一系列JSON响应信息（以字符串形式）。
        """

        # 解析JSON数据
        data = json.loads(message)
        # 取得本消息的id
        id = data['id']
        # 取得本消息的指令
        instruction = data['instruction']
        # 判断指令类型并生成回传响应信息
        result = []
        match instruction:
            case 'get_all_players_data': # 返回所有玩家的数据记录
                # 先获取当前时间（精确到小时且以半小时为准进行舍入，如11:30-12:29都归为12:00）
                now = datetime.now()
                cur_hour = 0
                if now.minute < 30:
                    cur_hour = now.hour
                else:
                    cur_hour = now.hour + 1
                    # 如果达到了24小时（到明天去了），归为0
                    if cur_hour >= 24:
                        cur_hour = 0
                # 再遍历当前的所有玩家的数据记录，依次以其为基准生成客户端响应JSON信息
                # 访问player_data_records前先加锁
                with player_data_records_lock:
                    for player, data in player_data_records.items():
                        # 遍历所有数据条目类型
                        for item in PLAYER_DATA_ITEMS:
                            # 注：此处能保证所有数据条目皆为整型
                            item_val = int(getattr(data, item))
                            json_data = {
                                'id': id,
                                'instruction': 'all_players_data',
                                'data': {
                                    'name': player,
                                    'type': item,
                                    'quantity': item_val,
                                    'time': cur_hour
                                }
                            }
                            result.append(json.dumps(json_data))
        
        # 返回JSON响应信息
        return result
    

    def stop(self) -> None:
        self.stop_event.set()


# 插件配置数据
plugin_config: PluginConfig = None
# MCDR 的 PluginServerInterface 对象，用于与 MCDR 的相关 API 交互
psi: PluginServerInterface = None
# 记录当前在线玩家（玩家名称）的列表
online_players: list[str] = []
# 函数执行结果的回调队列
mc_func_schedules: Queue[MCFuncResultSchedule] = Queue()
# 用于记录服务器上玩家数据的字典。键为玩家名称，值为 PlayerData 对象
player_data_records: dict[str, PlayerData] = {}
# 用于确保并发数据安全的线程同步锁
player_data_records_lock = None
# 一些需要用到的线程
server_monitor_thread: ServerMonitorThread = None
websocket_thread: WebsocketThread = None


def execute_msm_get_data(player: str, entry: str) -> int:
    # 生成符合MC命令语法的MC函数命令
    command = 'function msm:get_data {player:%s,entry:%s}' % (player, entry)
    # 将命令发送到MC服务器执行
    psi.execute(command)
    # 记录该函数执行结果的回调
    args = {'player': player, 'entry': entry}
    mc_func_schedules.put(MCFuncResultSchedule('msm:get_data', args, msm_get_data_callback))


def msm_get_data_callback(func: str, args: dict, result: int) -> None:
    global player_data_records

    # 获取本次回调对应的玩家名称
    player = args['player']
    # 查询字典中是否已注册有该玩家的信息
    exist_flag = False
    # 访问player_data_records前先加锁
    with player_data_records_lock:
        for name, data in player_data_records.items():
            if name == player:
                data.name = player
                # 若查找到，将MC服务器返回的信息更新到字典中去
                match args['entry']:
                    case 'msm_deathCount':
                        data.deathCount = result
                    case 'msm_playerKillCount':
                        data.playerKillCount = result
                    case 'msm_totalKillCount':
                        data.totalKillCount = result
                    case 'msm_health':
                        data.health = result
                    case 'msm_xp':
                        data.xp = result
                    case 'msm_level':
                        data.level = result
                    case 'msm_food':
                        data.food = result
                    case 'msm_air':
                        data.air = result
                    case 'msm_armor':
                        data.armor = result
                    case 'msm_placeBlockCount':
                        data.placeBlockCount = result
                    case 'msm_breakBlockCount':
                        data.breakBlockCount = result
                    case 'msm_onlineTime':
                        data.onlineTime = result
                player_data_records[player] = data
                # 将标志变量置为True
                exist_flag = True
                break
        # 若该玩家信息未注册，则创建新的PlayerData对象，并将MC服务器返回的信息更新到对象中
        if not exist_flag:
            data = PlayerData()
            data.name = player
            match args['entry']:
                case 'msm_deathCount':
                    data.deathCount = result
                case 'msm_playerKillCount':
                    data.playerKillCount = result
                case 'msm_totalKillCount':
                    data.totalKillCount = result
                case 'msm_health':
                    data.health = result
                case 'msm_xp':
                    data.xp = result
                case 'msm_level':
                    data.level = result
                case 'msm_food':
                    data.food = result
                case 'msm_air':
                    data.air = result
                case 'msm_armor':
                    data.armor = result
                case 'msm_placeBlockCount':
                    data.placeBlockCount = result
                case 'msm_breakBlockCount':
                    data.breakBlockCount = result
                case 'msm_onlineTime':
                    data.onlineTime = result
            player_data_records[player] = data

        # 打印调试信息
        psi.logger.debug(f'Player {player} data updated: {player_data_records[player]}')
        psi.logger.debug(f'Now the player data records: {player_data_records}')


# ---------------
# MCDR 事件回调函数
# ---------------


def on_load(server: PluginServerInterface, old) -> None:
    global plugin_config
    global psi
    global online_players, schedules, player_data_records
    global player_data_records_lock
    global server_monitor_thread, websocket_thread

    # 保存 PluginServerInterface 对象以供全局使用
    psi = server

    # 从 MCDR 加载插件配置
    plugin_config = psi.load_config_simple('config.json', target_class=PluginConfig)

    # 重新加载插件时，保持原有的数据不变
    if old:
        online_players = old.online_players if hasattr(old, 'online_players')\
            and old.online_players else []
        schedules = old.schedules if hasattr(old, 'schedules')\
            and old.schedules else []
        player_data_records = old.player_data_records if hasattr(old, 'player_data_records')\
            and old.player_data_records else {}

    # 重建线程同步锁
    player_data_records_lock = threading.RLock()

    # 重建并启动相关线程
    server_monitor_thread = ServerMonitorThread(plugin_config.serverMonitorThreadInterval)
    server_monitor_thread.start()
    websocket_thread = WebsocketThread(
        plugin_config.websocketThreadInterval,
        plugin_config.commIP,
        plugin_config.commPort
    )
    websocket_thread.start()

    server.logger.info(f'Plugin {PLUGIN_METADATA['name']} is now loaded')


def on_player_joined(server: PluginServerInterface, player: str, info: Info) -> None:
    # 当玩家加入，记录玩家到在线玩家列表
    online_players.append(player)
    server.logger.info(f'Player {player} joined the game')
    server.logger.info(f'Online players: {online_players}')
    
    # for debug purpose
    execute_msm_get_data(player, 'msm_onlineTime')


def on_player_left(server: PluginServerInterface, player: str) -> None:
    # 当玩家离开，从在线玩家列表中移除
    online_players.remove(player)
    server.logger.info(f'Player {player} left the game')
    server.logger.info(f'Online players: {online_players}')


def on_info(server: PluginServerInterface, info: Info) -> None:
    # 使用正则表达式判断该输出是否为MC服务器函数的执行结果
    pattern = r"Function [:\w]+ returned \d+"
    if not info.is_user and re.fullmatch(pattern, info.content):
        # 若是，解析该执行结果
        parts = info.content.split(' ')
        func = parts[1] # 取得函数名
        res = int(parts[3]) # 取得函数执行结果

        # 若回调列表不为空，取队列中回调并执行
        if not mc_func_schedules.empty():
            sched = mc_func_schedules.get()
            if sched.mc_func == func:
                sched.execute(res)


def on_unload(server: PluginServerInterface) -> None:
    print(f'Unloading plugin {PLUGIN_METADATA["name"]}...')

    # 卸载插件时，停止相关线程
    server_monitor_thread.stop()
    websocket_thread.stop()
