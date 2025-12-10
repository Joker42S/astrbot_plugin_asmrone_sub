# AstrBot ASMRONE_sub 插件

一个根据用于订阅asmr.one作品更新的AstrBot插件，定时查询符合筛选条件的最新作品并推送到群聊。
请合理设置刷新间隔和最大查询页数，避免浪费网站资源。如果有条件，请多多支持asmr.one的更新。

## 🛠️ 安装步骤

1. **克隆插件到AstrBot插件目录**
```bash
cd /path/to/astrbot/plugins
git clone https://github.com/Joker42S/astrbot_plugin_asmrone_sub.git
```

2. **重启AstrBot**
 
3. **配置参数**
   - 配置网站地址，或使用默认值
   - 如有必要，配置代理服务器
   - 自定义筛选条件


## 📖 使用方法

```bash
# 在群聊中发送，为该群聊订阅更新
/订阅ASMR

# 立即检查并推送一次更新
/刷新ASMR

## 📄 许可证

本项目遵循开源许可证，具体许可证信息请查看项目根目录下的 LICENSE 文件。