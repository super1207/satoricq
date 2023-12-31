# satoricq ~（WIP）~

All To Satori！

将[onebot](https://github.com/botuniverse/onebot-11)、[kook](https://developer.kookapp.cn/)、[大别野](https://webstatic.mihoyo.com/vila/bot/doc/)、[qq](https://bot.q.qq.com/wiki/develop/api)...协议转换到[satori](https://satori.js.org/zh-CN/)

愿景：我认为，需要有一种消息格式，用于连接各个机器人平台，让开发者能够专心致志的开发各类框架，应用。在很久以前，coolq http api做到了，之后是onebot11。然而现在面临着更大的挑战。随着两级群组的流行，这种结构，onebot11很难对其进行抽象；随着kook、大别野、qq频道等其它非qq群的聊天平台的出现，onebot11中的一些api，事件已经有些多余，增加了不少噪音；onebot11中特有的四种连接方法，对于协议实现者来说，是一种很大的负担，可以不存在或由其它中间件实现。

为什么是python写的：很简单，python写起来很容易，会python的人也较多，如果这个项目能被大家喜欢，即使我以后拒绝维护，其它人也可以改改接着用。我知道，python各种不太好部署，但是好部署的前提是项目可用。另外，我的虚拟主机只支持python、ruby和php，后两种完全不了解，python至少我写过，我现在想把bot部署在上面。

为什么是satori：我感觉很棒，它能同时接入很多不同的平台；协议描述很自然，我感觉我能理解；Satori有个Js/Ts实现，要是我弃坑了，也影响不会太大。

为什么叫satoricq：不知道，以后再想想，总能想出点意义来。

项目进展：OneBot、KOOK、大别野（mihoyo），qq部分已经可用了。目前，还不能对接Koishi的Satori Adapter插件，原因未知。现在你可以用[satori-python](https://github.com/RF-Tar-Railt/satori-python) 来体验satoricq。

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

我也不知道用什么版本的python好，建议用最新的。

记得安装`requirements.txt`里面的依赖，`pip install -r requirements.txt`

写好config.json后运行命令：`python satori.py`

如果报其它错误，你就看看代码，改一改，记得给我PR。如果你喜欢我...的项目，你可以加我的QQ群：920220179，如果这个群不小心满了，你就[文字加载中...]。

## Satori网络协议

HTTP API

WebSocket

WebHook（~暂未实现~暂不打算实现）

## onebot -> satori

注意，需要在onebot后台开启正向http和正向websocket

| 字段名          | 类型   | 默认值 | 说明                   | 例子                    |
|--------------|------|-----|----------------------|-----------------------|
| platform     | 文本   | -   | 固定为onebot            | onebot                |
| ws_url       | 文本   | -   | 用于接收事件的主动websocket地址 | ws://127.0.0.1:5800   |
| http_url     | 文本   | -   | 用于调用API的主动HTTP地址     | http://127.0.0.1:5700 |
| access_token | 文本或空 | 空   | onebot的access_token  | 77156                 |

**已实现事件：**

当消息被创建时触发（message-created）

群组成员增加时触发（guild-member-added）

**已实现消息元素类型：**

收：文本、at、at全体、图片

发：文本、at、at全体、图片

**已实现API：**

获取登录信息列表（管理接口）

获取登录信息（登录信息）

发送消息（消息）

获取群组成员（群组成员）

## kook -> satori


| 字段名          | 类型 | 默认值 | 说明                                                    | 例子                                  |
|--------------|----|-----|-------------------------------------------------------|-------------------------------------|
| platform     | 文本 | -   | 固定为kook                                               | kook                                |
| access_token | 文本 | -   | kook平台的token,见:https://developer.kookapp.cn/app/index | 1/MTUyNDY=/snqjxHpGZFdEM50wyZLOpg== |

**已实现事件：**

当消息被创建时触发（message-created）

群组成员增加时触发（guild-member-added）

**已实现消息元素类型：**

收：文本、at、at全体、图片

发：文本、at、at全体、图片

**已实现API：**

获取登录信息列表（管理接口）

获取登录信息（登录信息）

发送消息（消息）

获取群组成员（群组成员）

获取频道列表（频道）

获取用户信息（用户）


## mihoyo -> satori

注意：需要在米哈游后台开启websocket回调

| 字段名          | 类型 | 默认值 | 说明                                                    | 例子                                  |
|--------------|----|-----|-------------------------------------------------------|-------------------------------------|
| platform     | 文本 | -   | 固定为mihoyo  | mihoyo                                |
| bot_id | 文本 | -   | mihoyo平台的bot_id | bot_xxxxx |
| secret | 文本 | -   | mihoyo平台的secret | xxxxxxxxxxxxxxxxxxxxx |
| villa_id | 文本 | -   | mihoyo平台的villa_id(此配置项尚有争议，未来可能会有所变动) | 15881 |

**已实现事件：**

当消息被创建时触发（message-created）

**已实现消息元素类型：**

收：文本、at、at全体（实际收不到）、图片（实际收不到）

发：文本、at、at全体、图片

**已实现API：**

获取登录信息列表（管理接口）

获取登录信息（登录信息）

发送消息（消息）

获取群组成员（群组成员）


## qq -> satori

注意：目前，无论是私域还是公域，群聊还是频道，均需要at bot才能使bot收到事件。

发消息时，请在消息content中加入 `<passive id="xxxxxxx" />` 以指明要对哪条消息进行回复，否则对当前频道/群最近的消息进行回复。

| 字段名          | 类型 | 默认值 | 说明                                                    | 例子                                  |
|--------------|----|-----|-------------------------------------------------------|-------------------------------------|
| platform     | 文本 | -   | 固定为qq  | qq                                |
| botqq | 文本 | -   | qq平台的botqq | xxxxxxxxxxxxxxxxxxxxx |
| appid | 文本 | -   | qq平台的appid | xxxxxxxxxxxxxxxxxxxxx |
| token | 文本 | -   | qq平台的token| xxxxxxxxxxxxxxxxxxxxx |
| appsecret | 文本 | - | qq平台的appsecret | xxxxxxxxxxxxxxxxxxxxx |
| withgroup | 文本 | false | 是否接收QQ群消息，若你的账号没有这个权限，请不要开启，目前仅少部分账号和企业号有此权限 | true |

**已实现事件：**

当消息被创建时触发（message-created）（目前支持群聊和频道，暂不支持单聊）

**已实现消息元素类型：**

收：文本、at（仅频道支持）、at全体（实际收不到）

发：文本、at（仅频道支持）、at全体（实际发不出）、图片（仅频道支持）

**已实现API：**

获取登录信息列表（管理接口）

获取登录信息（登录信息）

发送消息（消息）

获取群组成员（群组成员）（目前仅支持频道）
