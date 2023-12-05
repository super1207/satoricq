# satoricq ~（WIP）~

All To Satori！

将[onebot](https://github.com/botuniverse/onebot-11)、[kook](https://developer.kookapp.cn/)、[大别野](https://webstatic.mihoyo.com/vila/bot/doc/)、[qq](https://bot.q.qq.com/wiki/develop/api)...协议转换到[satori](https://satori.js.org/zh-CN/)

愿景：我认为，需要有一种消息格式，用于连接各个机器人平台，让开发者能够专心致志的开发各类框架，应用。在很久以前，coolq http api做到了，之后是onebot11。然而现在面临者更大的挑战。随着两级群组的流行，这种结构，onebot11很难对其进行抽象；随着kook、大别野、qq频道等其它非qq群的聊天平台的出现，onebot11中的一些api，事件已经有些多余，增加了不少噪音；onebot11中特有的四种连接方法，对于协议实现者来说，是一种很大的负担，可以不存在或由其它中间件实现。

为什么是python写的：很简单，python写起来很容易，会python的人也较多，如果这个项目能被大家喜欢，即使我以后拒绝维护，其它人也可以改改接着用。我知道，python各种不太好部署，但是好部署的前提是项目可用。另外，我的虚拟主机只支持python、ruby和php，后两种完全不了解，python至少我写过，我现在想把bot部署在上面。

为什么是satori：我感觉很棒，它能同时接入很多不同的平台；协议描述很自然，我感觉我能理解；Satori有个Js/Ts实现，要是我弃坑了，也影响不会太大。

为什么叫SatoriCQ：不知道，以后再想想，总能想出点意义来。

项目进展：OneBot部分已经可用了。目前，还不能对接Koishi的Satori Adaptor插件，原因未知。

## 示例 config.json

```
{
    "botlist":[
        {
            "platform":"onebot",
            "ws_url":"ws://127.0.0.1:5800",
            "http_url":"http://127.0.0.1:5700",
            "access_token":"your onebot access_token"
        }
    ],
    "web_port": 8080,
    "web_host": "127.0.0.1",
    "access_token":"your satori token"
}
```
botlist：描述各个聊天平台的信息

web_port：satori对外的端口号(目前，API和事件共用一个端口号)

web_host：satori的主机地址，如果要允许外网访问，填"0.0.0.0"

web_path：暂时不支持设置，默认为空。

## 运行

我也不知道用什么版本的python好，反正你随便装一个，不行就卸了再换个版本。

写好config.json后运行命令：`python satori.py`

如果报`No module named 'XXX'`，你就用pip安装一下，我也不记得我用了哪些module了，如果报其它错误，你就看看代码，改一改，记得给我PR。如果你喜欢我...的项目，你可以加我的QQ群：920220179，如果这个群不小心满了，你就[文字加载中...]。

## Satori网络协议

HTTP API

WebSocket

WebHook（暂未实现）

## onebot -> satori

**已实现事件：**

当消息被创建时触发（message-created）

**已实现消息元素类型：**

收：文本、at、at全体、图片

发：文本、at、at全体、图片

**已实现API：**

获取登录信息列表（管理接口）

获取登录信息（登录信息）

发送消息（消息）

获取群组成员（群组成员）
