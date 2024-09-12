# 重置本数据包的所有记分板。

scoreboard objectives remove msm_deathCount
scoreboard objectives remove msm_playerKillCount
scoreboard objectives remove msm_totalKillCount
scoreboard objectives remove msm_health
scoreboard objectives remove msm_xp
scoreboard objectives remove msm_level
scoreboard objectives remove msm_food
scoreboard objectives remove msm_air
scoreboard objectives remove msm_armor

scoreboard objectives remove msm_placeBlockCount
scoreboard objectives remove msm_breakBlockCount
scoreboard objectives remove msm_onlineTime

function msm:init/scoreboard