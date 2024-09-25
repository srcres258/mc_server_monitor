from mcdreforged.api.all import *
from typing import Callable
import threading
import time
import asyncio
import websockets
import websockets.server
import json
from datetime import datetime
import copy
import os
import requests


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
    # 玩家数据更新线程（PlayerDataUpdateThread）的轮询间隔（单位：ms）
    playerDataUpdateThreadInterval: int = 1000
    # 远程网站服务器联络线程（WebsocketThread）的轮询间隔（单位：ms）
    websocketThreadInterval: int = 1000
    # 将要统计玩家数据的存档所在的目录（建议指定绝对路径以避免一些潜在的错误）
    worldDir: str = ''
    # 白名单文件（whitelist.json）所在的目录
    whitelistDir: str = ''


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


# MC玩家统计信息的所有条目
PLAYER_STATISTIC_ENTRIES: list[str] = [
    'minecraft:animals_bred', # 繁殖动物次数
    'minecraft:clean_armor', # 清洗盔甲次数
    'minecraft:clean_banner', # 清洗旗帜次数
    'minecraft:open_barrel', # 木桶打开次数
    'minecraft:bell_ring', # 鸣钟次数
    'minecraft:eat_cake_slice', # 吃掉的蛋糕片数
    'minecraft:fill_cauldron', # 炼药锅装水次数
    'minecraft:open_chest', # 箱子打开次数
    'minecraft:damage_absorbed', # 吸收的伤害
    'minecraft:damage_blocked_by_shield', # 盾牌抵挡的伤害
    'minecraft:damage_dealt', # 造成伤害
    'minecraft:damage_dealt_absorbed', # 造成伤害（被吸收）
    'minecraft:damage_dealt_resisted', # 造成伤害（被抵挡）
    'minecraft:damage_resisted', # 抵挡的伤害
    'minecraft:damage_taken', # 受到伤害
    'minecraft:inspect_dispenser', # 搜查发射器次数
    'minecraft:boat_one_cm', # 坐船移动距离
    'minecraft:aviate_one_cm', # 鞘翅滑行距离
    'minecraft:horse_one_cm', # 骑马移动距离
    'minecraft:minecart_one_cm', # 坐矿车移动距离
    'minecraft:pig_one_cm', # 骑猪移动距离
    'minecraft:strider_one_cm', # 骑炽足兽移动距离
    'minecraft:climb_one_cm', # 已攀爬距离
    'minecraft:crouch_one_cm', # 潜行距离
    'minecraft:fall_one_cm', # 摔落高度
    'minecraft:fly_one_cm', # 飞行距离
    'minecraft:sprint_one_cm', # 疾跑距离
    'minecraft:swim_one_cm', # 游泳距离
    'minecraft:walk_one_cm', # 行走距离
    'minecraft:walk_on_water_one_cm', # 水面行走距离
    'minecraft:walk_under_water_one_cm', # 水下行走距离
    'minecraft:inspect_dropper', # 搜查投掷器次数
    'minecraft:open_enderchest', # 末影箱打开次数
    'minecraft:fish_caught', # 捕鱼数
    'minecraft:leave_game', # 游戏退出次数
    'minecraft:inspect_hopper', # 搜查漏斗次数
    'minecraft:interact_with_anvil', # 与铁砧交互次数
    'minecraft:interact_with_beacon', # 与信标交互次数
    'minecraft:interact_with_blast_furnace', # 与高炉交互次数
    'minecraft:interact_with_brewingstand', # 与酿造台交互次数
    'minecraft:interact_with_campfire', # 与营火交互次数
    'minecraft:interact_with_cartography_table', # 与制图台交互次数
    'minecraft:interact_with_crafting_table', # 与工作台交互次数
    'minecraft:interact_with_furnace', # 与熔炉交互次数
    'minecraft:interact_with_grindstone', # 与砂轮交互次数
    'minecraft:interact_with_lectern', # 与讲台交互次数
    'minecraft:interact_with_loom', # 与织布机交互次数
    'minecraft:interact_with_smithing_table', # 与锻造台交互次数
    'minecraft:interact_with_smoker', # 与烟熏炉交互次数
    'minecraft:interact_with_stonecutter', # 与切石机交互次数
    'minecraft:drop', # 物品掉落
    'minecraft:enchant_item', # 物品附魔次数
    'minecraft:jump', # 跳跃次数
    'minecraft:mob_kills', # 生物击杀数
    'minecraft:play_record', # 播放唱片数
    'minecraft:play_noteblock', # 音符盒播放次数
    'minecraft:tune_noteblock', # 音符盒调音次数
    'minecraft:deaths', # 死亡次数
    'minecraft:pot_flower', # 盆栽种植数
    'minecraft:player_kills', # 玩家击杀数
    'minecraft:raid_trigger', # 触发袭击次数
    'minecraft:raid_win', # 袭击胜利次数
    'minecraft:clean_shulker_box', # 潜影盒清洗次数
    'minecraft:open_shulker_box', # 潜影盒打开次数
    'minecraft:time_since_death', # 自上次死亡
    'minecraft:time_since_rest', # 自上次入眠
    'minecraft:sneak_time', # 潜行时间
    'minecraft:talked_to_villager', # 村民交互次数
    'minecraft:target_hit', # 击中标靶次数
    'minecraft:play_time', # 游戏时长
    'minecraft:total_world_time', # 世界打开时间
    'minecraft:sleep_in_bed', # 躺在床上的次数
    'minecraft:traded_with_villager', # 村民交易次数
    'minecraft:trigger_trapped_chest', # 陷阱箱触发次数
    'minecraft:use_cauldron', # 从炼药锅取水次数
]


# 服务器上的玩家数据
class PlayerData(object):
    __slots__ = ('name', 'uuid','statistics')


    def __init__(self):
        # 玩家名称
        self.name: str = ''
        # 玩家的UUID
        self.uuid: str = ''
        # 玩家统计信息
        self.statistics: dict[str, int] = {}


class PlayerDataUpdateThread(threading.Thread):
    """
    用于时刻更新插件运行上下文中玩家数据的线程。
    """

    def __init__(self, interval: int):
        super().__init__()
        self.name = 'PlayerDataUpdateThread'
        self.daemon = False # 本线程不是守护线程，以确保插件运行上下文中玩家数据的完整性

        # 用于标识线程是否将要停止的信号量
        self.stop_event: threading.Event = threading.Event()
        # 本线程的轮询间隔（ms）
        self.interval: int = interval if interval > 0 else 1000 # 缺省值为1000ms


    def run(self) -> None:
        while not self.stop_event.is_set():
            try:
                # 先检查MC服务器是否已启动
                if psi.is_server_running():
                    # 定义玩家名称到UUID的字典
                    uuid_map = {}
                    # 遍历玩家的数据记录
                    with player_data_records_lock:
                        for name, record in player_data_records.items():
                            # 记录玩家名称和UUID
                            uuid_map[name] = record.uuid
                    # 遍历所建立的字典
                    for name, uuid in uuid_map.items():
                        # 根据所得玩家列表，对玩家数据依次进行同步
                        if not sync_player_statistics(name, uuid):
                            # 该玩家的数据同步失败
                            psi.logger.warning(f'Failed to synchronize player data for {name} ({uuid})')
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
        self.daemon = False # 本线程不是守护线程，以确保与远程网站服务器的交流不会被异常地中断

        # 用于标识线程是否将要停止的信号量
        self.stop_event: threading.Event = threading.Event()
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
                        for item in PLAYER_STATISTIC_ENTRIES:
                            # 注：此处能保证所有数据条目皆为整型
                            item_val = int(data.statistics.get(item, 0))
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
# 用于记录服务器上玩家数据的字典。键为玩家名称，值为 PlayerData 对象
player_data_records: dict[str, PlayerData] = {}
# 用于确保并发数据安全的线程同步锁
player_data_records_lock: threading.RLock = None
# 一些需要用到的线程
player_data_update_thread: PlayerDataUpdateThread = None
websocket_thread: WebsocketThread = None


def load_player_data_records() -> bool:
    """
    从白名单文件中加载玩家列表，并由此构建玩家数据记录。
    """

    # 构造白名单文件的路径
    whitelist_file_path = os.path.join(plugin_config.whitelistDir, 'whitelist.json')
    # 先判断白名单文件是否存在
    if not os.path.exists(whitelist_file_path):
        # 文件不存在，无法加载玩家列表
        psi.logger.warning(f'Whitelist file {whitelist_file_path} does not exist.')
        return False
    # 读取文件内容
    content = None
    with open(whitelist_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    # 判断是否读取成功
    if content is None or len(content) == 0:
        # 读取失败
        psi.logger.warning(f'Failed to load whitelist players from {whitelist_file_path}. '
                            'The list will remain empty or unchanged.')
        return False
    else:
        # 解析JSON数据
        data = json.loads(content)
        # 根据所得JSON数据构建玩家数据记录
        players = []
        for piece in data:
            # 读数据前先上锁
            with player_data_records_lock:
                players.append(piece['name'])
                # 先判断该玩家是否已存在于记录中
                if piece['name'] in player_data_records.keys():
                    # 若已存在，则更新其UUID
                    player_data_records[piece['name']].uuid = piece['uuid']
                else:
                    # 若不存在，则创建新的玩家数据记录
                    pd = PlayerData()
                    # 填入玩家名称和UUID
                    pd.name = piece['name']
                    pd.uuid = piece['uuid']
                    # 保存该记录
                    player_data_records[piece['name']] = pd
        
        psi.logger.info(f'Loaded {len(player_data_records)} players from the whitelist file: {", ".join(players)}')
        return True


def sync_player_statistics(name: str, uuid: str) -> bool:
    """
    从MC服务器存档目录中重新加载玩家的统计信息，将该玩家最新的统计信息同步到插件运行时上下文中。
    """

    # 判断函数参数是否合法
    if len(name) == 0 or len(uuid) == 0:
        return False

    # 定位到玩家统计信息所在目录
    stats_dir = os.path.join(plugin_config.worldDir, 'stats')
    # 定位到该玩家统计信息文件
    stats_file_name = f'{uuid}.json'
    stats_file_path = os.path.join(stats_dir, stats_file_name)

    # 先判断文件是否存在
    if os.path.exists(stats_file_path):
        # 若存在，则读取文件内容
        content = None
        with open(stats_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # 解析文件中的JSON数据
        data = json.loads(content)
        data_stats = data['stats']
        # 准备同步该玩家的数据
        with player_data_records_lock:
            # 先得到该玩家的统计信息条目
            player_data_record = player_data_records[name]
            for stat in data_stats.values(): # 忽略一级统计数据类型（统计数据命名空间）
                for k, v in stat.items():
                    # 先判断该统计数据类型是否是已知的（该统计数据条目是否合法）
                    if k in PLAYER_STATISTIC_ENTRIES:
                        # 若是，则更新玩家数据记录中的对应统计数据条目
                        player_data_record.statistics[k] = v
        return True
    else:
        # 文件不存在，无法更新该玩家的数据
        psi.logger.warning(f'Player {name} ({uuid}) has no statistics data file.')
        return False


# ---------------
# MCDR 事件回调函数
# ---------------


def on_load(server: PluginServerInterface, old) -> None:
    global plugin_config
    global psi
    global whitelist_players, schedules, player_data_records
    global player_data_records_lock
    global player_data_update_thread, websocket_thread

    # 保存 PluginServerInterface 对象以供全局使用
    psi = server

    # 从 MCDR 加载插件配置
    plugin_config = psi.load_config_simple('config.json', target_class=PluginConfig)

    # 重新加载插件时，保持原有的数据不变
    if old:
        whitelist_players = old.whitelist_players if hasattr(old, 'whitelist_players')\
            and old.whitelist_players != None else []
        schedules = old.schedules if hasattr(old, 'schedules')\
            and old.schedules != None else []
        player_data_records = old.player_data_records if hasattr(old, 'player_data_records')\
            and old.player_data_records != None else {}

    # 重建数据读写锁
    player_data_records_lock = threading.RLock()
        
    # 重新从白名单文件中加载玩家列表
    if not load_player_data_records():
        psi.logger.warning('Failed to load player data records from the whitelist file!')

    # 重建并启动相关线程
    player_data_update_thread = PlayerDataUpdateThread(plugin_config.playerDataUpdateThreadInterval)
    player_data_update_thread.start()
    websocket_thread = WebsocketThread(
        plugin_config.websocketThreadInterval,
        plugin_config.commIP,
        plugin_config.commPort
    )
    websocket_thread.start()

    server.logger.info(f'Plugin {PLUGIN_METADATA['name']} is now loaded')


def on_unload(server: PluginServerInterface) -> None:
    print(f'Unloading plugin {PLUGIN_METADATA["name"]}...')

    # 卸载插件时，停止相关线程
    player_data_update_thread.stop()
    websocket_thread.stop()
