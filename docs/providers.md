# 大模型 Provider 配置

项目使用统一客户端接口，正文生成与图表预读均可切换 provider。现有 MiMo 配置继续有效，无需安装厂商 SDK。

## 快速配置

查看支持的 provider、默认接口和环境变量：

```powershell
python -m paperdeepread list-providers
```

以 OpenAI 为例（模型 ID 可替换为账户中支持 Chat Completions 的模型）：

```powershell
python -m paperdeepread init-config --provider openai --model gpt-4.1 --path .paperdeepread.openai.toml
$env:OPENAI_API_KEY="your-key"
python -m paperdeepread run --input paper --output reports --config .paperdeepread.openai.toml --pdffigures2-jar .\pdffigures2\pdffigures2.jar
```

`init-config` 自动填写 provider 默认 API root 和 key 环境变量。除保留旧默认的 MiMo 外，需要显式指定 `--model`，不把会变化的模型列表写死。豆包可填写平台接受的模型 ID 或推理接入点 ID；聚合平台填写其完整模型 ID。已有配置文件不会覆盖，除非传入 `--force`。

## Provider 预设

| provider | 协议 | 默认 key 环境变量 | 默认 base_url |
|---|---|---|---|
| `mimo` | openai | `MIMO_API_KEY` | `https://token-plan-cn.xiaomimimo.com/v1` |
| `openai` | openai | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `anthropic` | anthropic | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` |
| `gemini` | gemini | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta` |
| `deepseek` | openai | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` |
| `qwen` | openai | `DASHSCOPE_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `moonshot` | openai | `MOONSHOT_API_KEY` | `https://api.moonshot.cn/v1` |
| `zhipu` | openai | `ZHIPU_API_KEY` | `https://open.bigmodel.cn/api/paas/v4` |
| `doubao` | openai | `ARK_API_KEY` | `https://ark.cn-beijing.volces.com/api/v3` |
| `minimax` | openai | `MINIMAX_API_KEY` | `https://api.minimax.cn/v1` |
| `xai` | openai | `XAI_API_KEY` | `https://api.x.ai/v1` |
| `openrouter` | openai | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| `siliconflow` | openai | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` |

另外支持 `openai_compatible`，用于自定义 OpenAI Chat Completions 网关及本地服务，必须指定 `base_url`。别名：`claude` → `anthropic`、`google` → `gemini`、`kimi` → `moonshot`、`glm` → `zhipu`、`dashscope` → `qwen`、`ark` → `doubao`、`grok` → `xai`。

Qwen、Moonshot、智谱、豆包和 MiniMax 的预设优先采用中国区接口。区域、普通 API 与订阅计划的 key/地址可能不同，应使用自己账户对应的 API root；例如 Moonshot 国际区可覆盖为 `https://api.moonshot.ai/v1`，MiniMax 国际区为 `https://api.minimax.io/v1`。`base_url` 是包含版本路径的 API root，不含 `/chat/completions`、`/messages` 或生成操作名。

## 最小配置

保留现有 `[pipeline]` 和 `[pdffigures2]`，只修改 `[llm]`：

```toml
[llm]
provider = "qwen"
model = "YOUR_MODEL_ID"
# base_url 和 api_key_env 省略时使用 provider 默认值
# api_key = "your-key"     # 也支持直接填写；建议使用环境变量
max_tokens = 8192
stream = true
```

上述 `YOUR_MODEL_ID` 是待替换占位符，不能原样运行。配置中的 `api_key` 优先于 `api_key_env` 对应环境变量；直接填写的 key 不出现在配置对象 repr 中，HTTP 错误信息会遮蔽当前 key。

## 正文与看图模型分开

不配置 `[vision]` 时，图表预读复用 `[llm]`。仅支持文本的模型也可以生成正文，但需另配具备图像理解能力的模型：

```toml
[llm]
provider = "deepseek"
model = "YOUR_TEXT_MODEL_ID"

[vision]
provider = "qwen"
model = "YOUR_VISION_MODEL_ID"
max_tokens = 4096
```

每个模型应使用平台实际开放的 ID，并替换占位符。配置两个 provider 的环境变量后运行同一个 `run` 命令。图表预读依然逐张发送 pdffigures2 图片，不会退化成只读图注。

`[vision]` 省略 provider 或选择相同 provider 时继承 `[llm]` 设置，可只覆盖 model；切换 provider 时使用新厂商默认值，避免错误继承原厂商地址、key、模型和额外参数。

## 自定义网关与本地模型

```toml
[llm]
provider = "openai_compatible"
base_url = "http://localhost:8000/v1"
model = "YOUR_LOCAL_MODEL_ID"
require_api_key = false
stream = true
```

无鉴权本地服务可显式设置 `require_api_key=false`；有鉴权的网关保留默认 true，并设置 `LLM_API_KEY` 或自定义 `api_key_env`。本地模型也需要支持图像输入，或者另配 `[vision]`。

## 模型参数差异

- `max_tokens` 是统一输出预算。OpenAI 和 MiniMax 默认发送 `max_completion_tokens`，其他兼容 provider 发送 `max_tokens`，Claude 使用原生 `max_tokens`，Gemini 使用 `maxOutputTokens`。可用 `max_tokens_parameter="max_tokens"` 或 `"max_completion_tokens"` 覆盖兼容协议的字段名。
- 新 provider 默认不发送 temperature，采用模型自身默认值，避免不支持自定义采样参数的模型返回 400。支持时可设置 `temperature=0.2`；`omit_temperature=true` 可显式省略。
- 不同模型的输出上限和推理预算不同，按模型能力调整 `max_tokens`；截断、空响应、工具调用、限制/拒绝或缺少正常结束标记的流不会当成完整报告。
- `timeout_seconds` 默认 900，`stream` 默认 true。请求失败时给出厂商名及错误，保留工作流断点；不自动反复请求。

兼容协议和 Claude 的额外原生参数通过 `[llm.extra_body]`（或 `[vision.extra_body]`）透传：

```toml
[llm.extra_body]
reasoning_effort = "low"
# 仅为语法示例：参数和值必须符合所选模型的文档
```

例如 Qwen 模型支持的 `enable_thinking` 可放在这里。MiniMax 默认发送 `reasoning_split=true`，把推理与最终正文分开。核心 model/messages/stream/token 字段禁止通过 extra_body 替换，以防工作流输入丢失。

Gemini 的生成参数使用其原生嵌套结构：

```toml
[llm.extra_body.generationConfig.thinkingConfig]
thinkingBudget = 0
```

这也是格式示例，所选模型是否接受 `thinkingBudget=0` 应以其官方文档为准。Gemini 的 `contents`、`systemInstruction` 及统一输出上限不能由额外参数覆盖。

## 实现与验证范围

OpenAI 兼容适配器、Anthropic Messages 和 Gemini generateContent 均支持流式与非流式响应。内部以统一的 text/image_url 消息表示论文内容，原生适配器转换成 Claude base64 image 或 Gemini inlineData；不会将 reasoning/thinking 响应块作为报告正文。

自动测试使用模拟 HTTP 响应核对请求地址、鉴权、图片编码、参数映射、流式事件、截断和报错路径，不代表每个厂商的账户权限或每个模型均已经实网验证。请选择具有相应文本/图像能力的模型，专用 Responses-only 模型、工具型端点、Azure/Bedrock/Vertex 等额外鉴权协议不在本次直接适配范围内，可经兼容网关接入。

接口依据官方文档实现：[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[Claude 图像输入](https://platform.claude.com/docs/en/build-with-claude/vision) 与 [流式事件](https://platform.claude.com/docs/en/build-with-claude/streaming)、[Gemini generateContent](https://ai.google.dev/api/generate-content)。

预设接口参考：[DeepSeek](https://api-docs.deepseek.com/)、[Qwen 百炼](https://help.aliyun.com/en/model-studio/base-url)、[Kimi](https://www.kimi.ai/help/kimi-api/api-troubleshooting)、[智谱](https://docs.bigmodel.cn/cn/guide/develop/openai/introduction)、[豆包方舟](https://docs.volcengine.com/docs/ark/chat-api?lang=zh)、[MiniMax](https://platform.minimax.cn/docs/api-reference/text-openai-api)、[xAI](https://docs.x.ai/developers/model-capabilities/legacy/chat-completions)、[OpenRouter](https://openrouter.ai/docs/api/api-reference/chat/create-a-chat-completion)、[SiliconFlow](https://docs.siliconflow.cn/docs/userguide/capabilities/text-generation)。
