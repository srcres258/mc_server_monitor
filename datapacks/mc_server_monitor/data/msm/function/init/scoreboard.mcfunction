# 玩家相关数据，通过记分板系统进行记录。

# -----
# 下列记分项为游戏自动更新。
# -----

# 死亡数
scoreboard objectives add msm_deathCount deathCount
# 击杀玩家数
scoreboard objectives add msm_playerKillCount playerKillCount
# 击杀数（包括玩家和生物）
scoreboard objectives add msm_totalKillCount totalKillCount
# 生命值（包括伤害吸收值）【只读】
scoreboard objectives add msm_health health
# 经验值【只读】
scoreboard objectives add msm_xp xp
# 等级【只读】
scoreboard objectives add msm_level level
# 饥饿值【只读】
scoreboard objectives add msm_food food
# 空气值【只读】
scoreboard objectives add msm_air air
# 护甲值【只读】
scoreboard objectives add msm_armor armor

# -----
# 下列记分项游戏不会自动更新，需通过监听游戏状态进行手动更新。
# -----

# 放置方块数
scoreboard objectives add msm_placeBlockCount trigger

# 破坏方块数
scoreboard objectives add msm_breakBlockCount trigger

# 在线时长（以游戏刻为单位）
# 注：受限于记分板数据类型（32位有符号整型），上限值为2,147,483,647，
# 也就是最多只能记录约1242.76天的时长。
scoreboard objectives add msm_onlineTime trigger